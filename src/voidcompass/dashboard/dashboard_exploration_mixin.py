"""Exploration intelligence lifecycle owned by the main application state."""

import logging
import time

from voidcompass.exploration.exploration_intelligence import (
    build_intelligence,
    checkpoint_payload,
)


EXPLORATION_INTELLIGENCE_TTL_S = 0.5


class DashboardExplorationMixin:
    def _invalidate_exploration_intelligence(self):
        self._exploration_intelligence_ts = 0.0

    def _exploration_intelligence_snapshot(self, compact=False):
        # Rebuilding deep-copies the Codex, checkpoint and milestone state under
        # the tracker lock, and a burst of Scan events asked for it repeatedly
        # from the same drain. Reuse holds only for the length of one burst, so
        # the packet still reflects the batch being processed.
        now = time.monotonic()
        intelligence = getattr(self, "_latest_exploration_intelligence", None)
        fresh = (
            intelligence is not None
            and (now - getattr(self, "_exploration_intelligence_ts", 0.0))
            < EXPLORATION_INTELLIGENCE_TTL_S
        )
        if not fresh:
            try:
                intelligence = build_intelligence(self)
            except Exception as exc:
                logging.debug("Exploration intelligence snapshot skipped: %s", exc)
                return {}
            self._exploration_intelligence_ts = now
        self._latest_exploration_intelligence = intelligence
        if compact:
            intelligence = dict(intelligence)
            completion = dict(intelligence.get("completion") or {})
            completion.pop("body_rows", None)
            intelligence["completion"] = completion
            intelligence["actions"] = [
                dict(row) for row in list(intelligence.get("actions") or [])[:5]
            ]
            intelligence["milestones"] = [
                dict(row) for row in list(intelligence.get("milestones") or [])[-4:]
            ]
        return intelligence

    def _save_exploration_checkpoint(self, reason="app-close", immediate=False):
        tracker = getattr(self, "deep_survey", None)
        if not tracker:
            return {}
        # A checkpoint is the record a commander resumes from, so it always
        # rebuilds rather than accepting a packet cached during a burst. The
        # fresh packet is then reused by whatever reads it next.
        self._invalidate_exploration_intelligence()
        try:
            return tracker.update_checkpoint(
                checkpoint_payload(
                    self, reason,
                    intelligence=self._exploration_intelligence_snapshot(),
                ),
                immediate=immediate,
            )
        except Exception as exc:
            logging.debug("Exploration checkpoint skipped [%s]: %s", reason, exc)
            return {}

    def _update_exploration_intelligence(self, ev, raw, startup_replay=False):
        tracker = getattr(self, "deep_survey", None)
        if not tracker:
            return
        relevant = {
            "LoadGame", "Location", "FSDJump", "CarrierJump", "Docked", "Shutdown",
            "FSSDiscoveryScan", "FSSAllBodiesFound", "Scan", "SAAScanComplete",
            "SAASignalsFound", "ScanOrganic", "CodexEntry", "Screenshot",
            "HullDamage", "RepairAll", "Loadout", "Synthesis", "JetConeBoost",
        }
        if ev not in relevant:
            return
        self._invalidate_exploration_intelligence()
        timestamp = raw.get("timestamp") if isinstance(raw, dict) else None
        try:
            milestones = tracker.evaluate_milestones(
                current_bodies=getattr(self, "scan_items", None) or (),
                timestamp=timestamp,
            )
        except Exception as exc:
            logging.debug("Exploration milestone evaluation skipped [%s]: %s", ev, exc)
            milestones = []
        intelligence = self._exploration_intelligence_snapshot()
        regions = intelligence.get("regions") or {}
        current_region = regions.get("current") or {}
        try:
            self.achievement_engine.process_event({
                "type": "VoidCompassRegionPassport",
                "event": "VoidCompassRegionPassport",
                "VisitedRegions": int(regions.get("visited") or 0),
                "RegionID": current_region.get("id"),
                "RegionName": current_region.get("name"),
            }, notify=not startup_replay, historical=startup_replay)
        except Exception:
            pass
        if ev in {"Docked", "Shutdown"}:
            self._save_exploration_checkpoint(ev.casefold(), immediate=ev == "Shutdown")
        if ev == "LoadGame" and not startup_replay:
            checkpoint = intelligence.get("checkpoint") or {}
            checkpoint_key = str(checkpoint.get("saved_at") or "")
            if checkpoint_key and checkpoint_key != getattr(self, "_exploration_resume_feed_key", None):
                self._exploration_resume_feed_key = checkpoint_key
                completion = checkpoint.get("completion") or {}
                next_waypoint = checkpoint.get("next_waypoint") or "no plotted waypoint"
                self.add_event_feed_entry(
                    "EXPEDITION",
                    f"Resume checkpoint: {checkpoint.get('system') or 'unknown system'} · "
                    f"{completion.get('summary') or 'survey state retained'} · next {next_waypoint}",
                    severity="INFO",
                )
        if not milestones or startup_replay:
            return
        for milestone in milestones:
            title = str(milestone.get("title") or "Exploration milestone")
            detail = str(milestone.get("detail") or "")
            self.add_event_feed_entry("MILESTONE", f"{title} · {detail}", severity="INFO")
            if ev != "Shutdown" and getattr(self, "captains_log", None):
                self.captains_log.add_manual_highlight("MILESTONE", title, detail)
