"""Overlay groups on the deck (5.8.1): kept per commander, switched by hand
(hotkeys, the deck header, Overlay Studio, the Local API) or by what you're
doing, and hidden through the same overrides as the maps and menus, so the
windows stay up and come back at once."""
from __future__ import annotations

import logging
import time

from voidcompass.core import overlay_groups
from voidcompass.core.overlay_registry import OVERLAY_SPEC_BY_ATTR


class DashboardOverlayGroupsMixin:
    def _overlay_groups(self):
        config = getattr(self, "config", None) or {}
        return overlay_groups.normalize_groups(config.get("overlay_groups"), known=set(OVERLAY_SPEC_BY_ATTR))

    def _overlay_group_state(self, groups=None):
        config = getattr(self, "config", None) or {}
        return overlay_groups.normalize_state(config.get("overlay_group_state"), groups or self._overlay_groups())

    def _overlay_groups_hidden(self):
        """The overlay ids the groups hide now (merged into the overrides)."""
        groups = self._overlay_groups()
        if not groups:
            return set()
        attrs = overlay_groups.hidden(groups, self._overlay_group_state(groups), OVERLAY_SPEC_BY_ATTR)
        return {OVERLAY_SPEC_BY_ATTR[attr].overlay_id for attr in attrs if attr in OVERLAY_SPEC_BY_ATTR}

    def _overlay_groups_apply(self, state, switched_on=()):
        """Keep the new state, turn on any member of a group just switched on
        that's off, and show and hide the overlays to match."""
        groups = self._overlay_groups()
        self.config["overlay_group_state"] = state
        enable = [OVERLAY_SPEC_BY_ATTR[attr].enabled_key for group in groups if group["id"] in switched_on
                  for attr in group["members"] if attr in OVERLAY_SPEC_BY_ATTR
                  and OVERLAY_SPEC_BY_ATTR[attr].enabled_key and not self.config.get(OVERLAY_SPEC_BY_ATTR[attr].enabled_key)]
        for key in enable:
            self.config[key] = True
        if enable:
            try:
                self._apply_runtime_feature_toggles()
            except Exception:
                logging.debug("Group members not switched on", exc_info=True)
        persist = getattr(self, "_persist_config", None)
        if callable(persist):
            persist()
        apply_hiding = getattr(self, "_apply_map_overlay_hiding", None)
        if callable(apply_hiding):
            apply_hiding()
        publish = getattr(self, "_schedule_html_dashboard_publish", None)
        if callable(publish):
            publish(immediate=True)
        return state

    def _overlay_group_toggle(self, group_id, on=None, say=True):
        """A group switched by hand. True when it changed."""
        groups = self._overlay_groups()
        group = next((row for row in groups if row["id"] == group_id), None)
        if group is None:
            return False
        before = self._overlay_group_state(groups)
        after = overlay_groups.toggle(groups, before, group_id, on)
        if after == before:
            return False
        now_on = overlay_groups.is_on(group, after)
        self._overlay_groups_apply(after, switched_on=(group_id,) if now_on else ())
        if say:
            toast = getattr(self, "toast_hud", None)
            if toast is not None and hasattr(toast, "push"):
                words = ("only these showing" if group["mode"] == "only" else "showing") if now_on else "hidden"
                toast.push("OVERLAY GROUP", f"{group['name']} · {words}", severity="info", duration_s=2.5)
        return True

    def _overlay_group_slot(self, slot):
        """Group hotkey ``slot`` (1 to MAX_GROUPS): the group in that place."""
        groups = self._overlay_groups()
        if 1 <= slot <= len(groups):
            return self._overlay_group_toggle(groups[slot - 1]["id"])
        toast = getattr(self, "toast_hud", None)
        if toast is not None and hasattr(toast, "push"):
            toast.push("OVERLAY GROUP", f"No group {slot} yet: make one in Overlay Studio", severity="warn", duration_s=3.0)
        return False

    def _overlay_groups_watch(self, force=False):
        """What you're doing, checked as it changes (at most once a second):
        groups tied to an activity follow it."""
        groups = self._overlay_groups()
        if not any(group["activity"] for group in groups):
            return False
        moment = time.monotonic()
        if not force and moment - getattr(self, "_overlay_groups_checked", 0.0) < 1.0:
            return False
        self._overlay_groups_checked = moment
        facts_of = getattr(self, "_hud_pages_facts", None)
        try:
            facts = dict(facts_of()) if callable(facts_of) else {}
        except Exception:
            facts = {}
        facts["on_foot"] = bool(getattr(self, "current_on_foot", False))
        activity = overlay_groups.activity_of(facts)
        before = self._overlay_group_state(groups)
        after = overlay_groups.follow_activity(groups, before, activity)
        if after == before:
            return False
        switched_on = [group_id for group_id in after["auto"] if group_id not in before["auto"]]
        self._overlay_groups_apply(after, switched_on=switched_on)
        return True

    def _overlay_groups_brief(self):
        """The groups for the deck header and the Local API."""
        groups = self._overlay_groups()
        state = self._overlay_group_state(groups)
        return {"groups": [{"id": group["id"], "name": group["name"], "mode": group["mode"], "activity": group["activity"],
                            "members": list(group["members"]), "on": overlay_groups.is_on(group, state),
                            "auto": group["id"] in state["auto"], "slot": index + 1}
                           for index, group in enumerate(groups)],
                "activity": state.get("activity", "")}

    # -- Overlay Studio: making them ---------------------------------------------
    def _overlay_group_save(self, payload):
        """Make a group, or change one (by id)."""
        groups = list(self.config.get("overlay_groups") or [])
        group_id = str(payload.get("id") or "")
        row = {"id": group_id or payload.get("name"), "name": payload.get("name"), "mode": payload.get("mode"),
               "members": payload.get("members") or [], "activity": payload.get("activity") or ""}
        index = next((index for index, item in enumerate(groups) if isinstance(item, dict) and item.get("id") == group_id), None)
        if index is None:
            if len(overlay_groups.normalize_groups(groups)) >= overlay_groups.MAX_GROUPS:
                return False
            groups.append(row)
        else:
            groups[index] = {**groups[index], **row, "id": group_id}
        cleaned = overlay_groups.normalize_groups(groups, known=set(OVERLAY_SPEC_BY_ATTR))
        if not any(item["name"] == str(payload.get("name") or "").strip()[:40] for item in cleaned):
            return False
        self.config["overlay_groups"] = cleaned
        self._overlay_groups_apply(self._overlay_group_state(cleaned))
        self._overlay_groups_watch(force=True)
        return True

    def _overlay_group_delete(self, group_id):
        groups = [item for item in self._overlay_groups() if item["id"] != group_id]
        if len(groups) == len(self._overlay_groups()):
            return False
        self.config["overlay_groups"] = groups
        self._overlay_groups_apply(self._overlay_group_state(groups))
        return True

    def _overlay_group_move(self, group_id, step):
        """Up or down the list (its place is its hotkey)."""
        groups = self._overlay_groups()
        index = next((index for index, item in enumerate(groups) if item["id"] == group_id), None)
        target = None if index is None else index + (1 if int(step or 0) > 0 else -1)
        if index is None or not 0 <= target < len(groups):
            return False
        groups[index], groups[target] = groups[target], groups[index]
        self.config["overlay_groups"] = groups
        self._overlay_groups_apply(self._overlay_group_state(groups))
        return True

    def _overlay_group_member(self, group_id, attr, member):
        """Overlay Studio's inspector (5.8.3): this overlay in that group, or not."""
        if attr not in OVERLAY_SPEC_BY_ATTR:
            return False
        groups = self._overlay_groups()
        group = next((row for row in groups if row["id"] == group_id), None)
        if group is None or (attr in group["members"]) == bool(member):
            return False
        group["members"] = [*group["members"], attr] if member else [item for item in group["members"] if item != attr]
        self.config["overlay_groups"] = groups
        self._overlay_groups_apply(self._overlay_group_state(groups), switched_on=(group_id,) if member and overlay_groups.is_on(
            group, self._overlay_group_state(groups)) else ())
        return True

    def _overlay_group_talk(self, text, rng=None):
        """A group asked for by name, by TALK or voice (5.8.3): its reply, or
        None when no group was asked about."""
        from voidcompass.overlays import watcher_copilot
        groups = self._overlay_groups()
        asked = overlay_groups.request(text, groups)
        if asked is None:
            return None
        if not groups:
            return watcher_copilot.reply("group_none", rng)
        if asked["id"] is None:
            return watcher_copilot.reply("group_unknown", rng, name=asked["name"],
                                         names=", ".join(group["name"] for group in groups))
        group = next(row for row in groups if row["id"] == asked["id"])
        was = overlay_groups.is_on(group, self._overlay_group_state(groups))
        want = (not was) if asked["on"] is None else asked["on"]
        if want == was:
            return watcher_copilot.reply("group_already_on" if was else "group_already_off", rng, name=group["name"])
        self._ui_post(lambda: self._overlay_group_toggle(group["id"], on=want, say=False), key="talk-group")
        return watcher_copilot.reply("group_on" if want else "group_off", rng, name=group["name"])

    # -- the Local API --------------------------------------------------------------
    def api_overlay_groups(self):
        return self._overlay_groups_brief()

    def api_overlay_group_toggle(self, group_id, on=None):
        from voidcompass.services.local_api import ApiError
        if not any(group["id"] == group_id for group in self._overlay_groups()):
            raise ApiError(404, f"No overlay group '{group_id}'")
        changed = self._overlay_group_toggle(group_id, on=on, say=False)
        return {"changed": changed, **self._overlay_groups_brief()}
