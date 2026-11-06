"""Axiom, Meridian and Lyra: full companions on the shared officer-style mind (5.7.4, Lyra 5.7.6)."""
from voidcompass.core import companions
from voidcompass.overlays import companion_personas
from voidcompass.overlays.aster_mind import AsterMind

TEST_LINES = {identity: companion_personas.get(identity).test_line for identity in companions.NEW_IDENTITIES}


def command_reply(outcome, rng, fields):
    """Control acknowledgements in the active persona's own words."""
    persona = companion_personas.get(getattr(rng, "companion_identity", "")) or companion_personas.get("aster")
    return persona.lines.command_reply(outcome, rng, fields)


class CrewMind(AsterMind):
    def __init__(self, memory_path=None, config=None, **kwargs):
        self.identity = companions.identity(config)
        super().__init__(memory_path, config, **kwargs)
