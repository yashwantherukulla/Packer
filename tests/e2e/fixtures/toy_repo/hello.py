"""A boring, obviously-benign module. Static + dynamic passes must find nothing high-severity."""


def greet(name: str) -> str:
    return f"hello, {name}"


def add(a: int, b: int) -> int:
    return a + b


if __name__ == "__main__":
    print(greet("world"))
    print(add(2, 3))
