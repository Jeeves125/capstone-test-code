class Float2:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def normalize(self) -> 'Float2':
        length = (self.x**2 + self.y**2) ** 0.5
        if length == 0:
            return Float2(0, 0)
        return Float2(self.x / length, self.y / length)
    
    def magnitude(self) -> float:
        return (self.x**2 + self.y**2) ** 0.5

    def __sub__(self, other: 'Float2') -> 'Float2':
        return Float2(self.x - other.x, self.y - other.y)

    def __mul__(self, other: float) -> 'Float2':
        return Float2(self.x * other, self.y * other)

    def __truediv__(self, other: float) -> 'Float2':
        return Float2(self.x / other, self.y / other)
    
    def __add__(self, other: 'Float2') -> 'Float2':
        return Float2(self.x + other.x, self.y + other.y)
    
    def __str__(self):
        return f"Float2({self.x}, {self.y})"