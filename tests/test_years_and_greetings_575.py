"""Years said as years, and "hello" for the whole crew (5.7.5)."""
import random
import unittest

from voidcompass.core import companions, voice_commands
from tests.test_aster_companion import Clock
from voidcompass.overlays import watcher_chat
from voidcompass.voice.watcher_voice import speakable, year_words


class YearTests(unittest.TestCase):
    def test_years_read_the_way_people_say_them(self):
        for number, words in ((1998, "nineteen ninety-eight"), (1900, "nineteen hundred"), (1905, "nineteen oh five"),
                              (2000, "two thousand"), (2005, "two thousand five"), (2026, "twenty twenty-six"),
                              (3312, "thirty-three twelve"), (3301, "thirty-three oh one"), (3300, "thirty-three hundred"),
                              (1111, "eleven eleven")):
            self.assertEqual(year_words(number), words, number)

    def test_speech_says_years_but_leaves_counts_alone(self):
        for text, said in (("Born in 1998, apparently.", "Born in nineteen ninety-eight, apparently."),
                           ("It is 3312 now.", "It is thirty-three twelve now."),
                           ("In 1998. Then 2001!", "In nineteen ninety-eight. Then two thousand one!"),
                           ("1500 tonnes refined.", "1500 tonnes refined."),
                           ("Jump of 1200 ly.", "Jump of 1200 light years."),
                           ("2048 Cr in the bank.", "2048 credits in the bank."),
                           ("3,000 light years.", "3,000 light years."),
                           ("1,998 tonnes", "1,998 tonnes"),
                           ("We made 1250 jumps.", "We made 1250 jumps."),
                           ("Fuel 1998.5", "Fuel 1998.5"),
                           ("HIP 103855", "HIP 103855"),
                           ("LHS 3447 and HIP 1998", "LHS 3447 and HIP 1998"),
                           ("Last here in 3310 at LHS 3006.", "Last here in thirty-three ten at LHS 3006."),
                           ("Since 1066 nothing.", "Since 1066 nothing.")):
            self.assertEqual(speakable(text), said, text)


class GreetingTests(unittest.TestCase):
    def test_hello_to_any_companion(self):
        for text in ("hello", "hello watcher", "hello the watcher", "hi axiom", "hey meridian", "hello aster",
                     "hello there commander", "Hello, Meridian!"):
            self.assertEqual(watcher_chat.intent(text), "greeting", text)
            self.assertTrue(voice_commands.native_request(text, None, kind="chat"), text)
        for text in ("meridian what can you do", "what can you do axiom", "the watcher, what can you do"):
            self.assertEqual(watcher_chat.intent(text), "capabilities", text)
        self.assertIsNone(watcher_chat.intent("hello bob"))

    def test_the_command_is_no_longer_named_for_the_watcher(self):
        greeting = next(command for command in voice_commands.catalogue(None) if command.id == "app_greeting")
        self.assertEqual(greeting.example, "hello")
        self.assertNotIn("watcher", " ".join(greeting.phrases))


class CrewGreetingDepthTests(unittest.TestCase):
    def test_every_companion_has_as_many_greetings_and_rundowns(self):
        for identity in ("aster", "axiom", "meridian", "lyra"):
            config = {"companion_identity": identity, f"{identity}_thoughts": "chatty"}
            companion = companions.create_mind(None, config, clock=Clock(), rng=random.Random(2))
            for phrase, size in ((f"hello {identity}", 50), ("what can you do", 10)):
                heard = set()
                for _ in range(size):
                    companion.talk(phrase)
                    heard.add(companion.thought["text"])
                self.assertEqual(len(heard), size, (identity, phrase, "every one before any repeats"))
        self.assertEqual(len(watcher_chat.GREETINGS), 50)
        self.assertEqual(len(watcher_chat.CAPABILITIES), 10)


if __name__ == "__main__":
    unittest.main()
