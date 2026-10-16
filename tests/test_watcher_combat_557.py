"""5.5.7: the Watcher in a fight. Hull damage and a critical hull, shields
back, kills and combat bonds, an interdiction given in to, combat zones, a
fight that ends on its own after a quiet spell, and fights on foot, which
the game never logs as an attack (Status.json's health tells it instead)."""

from types import SimpleNamespace
import unittest

from voidcompass.overlays import watcher_lines
from voidcompass.overlays.watcher_mind import CALM_S, COMBAT_TOPICS, IMPORTANCE
from tests.test_watcher_mind import Clock, mind


class CombatTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.watcher = mind(clock=self.clock)
        self.watcher.observe("LoadGame", {})

    def later(self, seconds=60):
        self.clock.now += seconds

    def topic(self, event, raw=None):
        self.later()
        thought = self.watcher.observe(event, dict(raw or {}))
        return thought and thought["topic"]

    def test_every_fight_topic_has_forty_lines_in_both_voices(self):
        for topic in COMBAT_TOPICS:
            self.assertIn(topic, IMPORTANCE)
            for bank in (watcher_lines.NORMAL, watcher_lines.WEARY):
                self.assertGreaterEqual(len(bank[topic]), 40, topic)

    def test_the_hull_warns_once_then_again_when_critical(self):
        self.later()
        thought = self.watcher.observe("HullDamage", {"Health": .55, "PlayerPilot": True, "Fighter": False})
        self.assertEqual(thought["topic"], "hull_damage")
        self.assertIn("55", thought["text"])
        self.assertIsNone(self.topic("HullDamage", {"Health": .5, "PlayerPilot": True}), "said already")
        self.assertEqual(self.topic("HullDamage", {"Health": .2, "PlayerPilot": True}), "hull_critical")
        self.assertIsNone(self.topic("HullDamage", {"Health": .4, "Fighter": True}), "the fighter's hull isn't ours")
        self.topic("RepairAll")
        self.assertEqual(self.topic("HullDamage", {"Health": .5, "PlayerPilot": True}), "hull_damage", "repaired: it warns again")

    def test_shields_interdictions_kills_and_zones(self):
        self.assertEqual(self.topic("ShieldState", {"ShieldsUp": False}), "danger")
        self.assertEqual(self.topic("ShieldState", {"ShieldsUp": True}), "shields_back")
        self.assertIsNone(self.topic("ShieldState", {"ShieldsUp": True}), "they were never down")
        self.assertEqual(self.topic("Interdicted", {"Submitted": True}), "interdiction_submitted")
        self.later(400)  # "danger" rests a while once said
        self.assertEqual(self.topic("Interdicted", {"Submitted": False}), "danger")
        self.later(400)
        thought = self.watcher.observe("FactionKillBond", {"Reward": 45000, "AwardingFaction_Localised": "Alliance"})
        self.assertEqual(thought["topic"], "combat_win")
        self.assertIsNone(self.topic("PVPKill", {"Victim": "Jameson"}), "one kill remark per spell, not one per kill")
        self.later(400)
        self.assertEqual(self.topic("PVPKill", {"Victim": "Jameson"}), "combat_win")
        self.assertEqual(self.topic("SupercruiseDestinationDrop", {"Type": "$Warzone_PointRace_High:#index=1;"}),
                         "combat_zone")
        self.assertNotEqual(self.topic("SupercruiseDestinationDrop", {"Type": "$MULTIPLAYER_SCENARIO42_TITLE;"}),
                            "combat_zone")

    def test_a_fight_ends_after_a_quiet_spell(self):
        self.topic("UnderAttack", {"Target": "You"})
        self.later(CALM_S / 2)
        self.assertIsNone(self.watcher.tick())
        self.watcher.vitals(in_danger=True)  # the game still says danger: the fight goes on
        self.later(CALM_S - 1)
        self.assertNotEqual((self.watcher.tick() or {}).get("topic"), "danger_over")
        self.watcher.vitals(in_danger=False)
        self.later(CALM_S + 1)
        self.assertEqual(self.watcher.tick()["topic"], "danger_over")
        self.assertFalse(self.watcher._in_danger)

    def test_shields_down_holds_the_fight_open(self):
        self.topic("ShieldState", {"ShieldsUp": False})
        self.later(CALM_S + 1)
        self.assertNotEqual((self.watcher.tick() or {}).get("topic"), "danger_over")
        self.topic("ShieldState", {"ShieldsUp": True})
        self.later(CALM_S + 1)
        self.assertEqual(self.watcher.tick()["topic"], "danger_over")

    def test_a_fight_on_foot_is_felt_through_the_health_bar(self):
        self.topic("Disembark", {"OnPlanet": True})
        self.later()
        self.assertIsNone(self.watcher.vitals(on_foot=True, health=1.0))
        self.later(2)
        thought = self.watcher.vitals(on_foot=True, health=.78)
        self.assertEqual(thought["topic"], "foot_danger")
        self.later(2)
        self.assertIsNone(self.watcher.vitals(on_foot=True, health=.6), "it said so already")
        self.later()
        self.assertEqual(self.watcher.observe("FactionKillBond", {"Reward": 9000})["topic"], "foot_win")
        self.later(CALM_S + 1)
        self.assertEqual(self.watcher.tick()["topic"], "foot_danger_over")

    def test_low_health_counts_and_getting_back_aboard_ends_it(self):
        self.topic("Disembark", {})
        self.later()
        self.assertEqual(self.watcher.vitals(on_foot=True, health=.3, low_health=True)["topic"], "foot_danger")
        self.later(CALM_S + 1)
        self.watcher.vitals(on_foot=True, health=.3, low_health=True)
        self.assertNotEqual((self.watcher.tick() or {}).get("topic"), "foot_danger_over", "still low")
        self.assertEqual(self.topic("Embark", {}), "foot_danger_over")

    def test_dying_on_foot_has_its_own_words(self):
        self.topic("Disembark", {})
        self.assertEqual(self.topic("Died", {}), "died_foot")
        self.topic("Resurrect", {})
        self.assertEqual(self.topic("Died", {}), "died")

    def test_a_dropship_to_a_ground_war(self):
        self.assertEqual(self.topic("BookDropship", {"DestinationSystem": "Sol"}), "dropship")

    def test_the_orb_hands_on_foot_health_to_the_mind(self):
        from voidcompass.overlays.heartbeat_hud import HeartbeatHUD

        heard = {}
        hud = HeartbeatHUD.__new__(HeartbeatHUD)
        for name, value in {"_pulse_serial": 0, "_activity_state": "FLIGHT", "_status_serial": 0,
                            "_events": [], "_event_serial": 0}.items():
            setattr(hud, name, value)
        hud.mind = SimpleNamespace(vitals=lambda *args, **kwargs: heard.update(kwargs))
        hud._redraw = lambda: None
        hud.pulse("status", "STATUS", "ON FOOT", {"Flags": 0, "Flags2": 0x01 | 0x80, "Health": .4})
        self.assertEqual(heard, {"health": .4, "low_health": True, "on_foot": True, "in_danger": False})


if __name__ == "__main__":
    unittest.main()
