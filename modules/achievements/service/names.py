"""Anonymous leaderboard names (A16): WildCrab, SpeedyTurtle. Stable for a run, unique per
student, and not reversible without the seed. Pure: no I/O."""

import hashlib

ADJECTIVES = [
    "Wild", "Speedy", "Sleepy", "Brave", "Clever", "Cheeky", "Dizzy", "Fuzzy", "Gentle", "Grumpy",
    "Happy", "Jolly", "Lazy", "Lucky", "Mighty", "Nimble", "Plucky", "Quiet", "Rowdy", "Sneaky",
    "Snazzy", "Spicy", "Sunny", "Swift", "Tiny", "Witty", "Zany", "Bouncy", "Cosmic", "Dapper",
    "Fluffy", "Giddy", "Humble", "Jazzy", "Kindly", "Loyal", "Merry", "Noble", "Peppy", "Zesty",
]
ANIMALS = [
    "Crab", "Turtle", "Otter", "Panda", "Fox", "Owl", "Badger", "Beaver", "Camel", "Dolphin",
    "Falcon", "Gecko", "Heron", "Ibis", "Koala", "Lemur", "Llama", "Moose", "Newt", "Osprey",
    "Penguin", "Quokka", "Raccoon", "Seal", "Tiger", "Walrus", "Yak", "Zebra", "Alpaca", "Bison",
    "Cobra", "Donkey", "Ferret", "Goat", "Hedgehog", "Iguana", "Jaguar", "Kiwi", "Lynx", "Mole",
]
CAPACITY = len(ADJECTIVES) * len(ANIMALS)


class NameBook:
    def __init__(self, seed, assigned=None):
        self.seed = str(seed)
        self.assigned = dict(assigned or {})

    def name_for(self, user):
        """The student's name; the same answer every time. Collisions probe to the next free
        slot, then fall back to a numbered name once the 1600 combinations run out."""
        if user in self.assigned:
            return self.assigned[user]
        taken = set(self.assigned.values())
        digest = hashlib.sha256(f"{self.seed}:{user}".encode()).digest()
        start = int.from_bytes(digest[:4], "big") % CAPACITY
        for step in range(CAPACITY):
            slot = (start + step) % CAPACITY
            name = ADJECTIVES[slot % len(ADJECTIVES)] + ANIMALS[slot // len(ADJECTIVES)]
            if name not in taken:
                self.assigned[user] = name
                return name
        n = len(self.assigned) + 1
        while f"Student{n}" in taken:
            n += 1
        self.assigned[user] = f"Student{n}"
        return self.assigned[user]

    def mapping(self):
        """The facilitator's real-name view: {user: anonymous name}."""
        return dict(self.assigned)
