class Float3:
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z

        self.on_changed: callable = None
        
    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)
    
    def normalize(self) -> 'Float3':
        length = (self.x**2 + self.y**2 + self.z**2) ** 0.5
        if length == 0:
            return Float3(0, 0, 0)
        return Float3(self.x / length, self.y / length, self.z / length)

    def cross(self, other: 'Float3') -> 'Float3':
        return Float3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x
        )
        
    def distance_to(self, other: 'Float3') -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2) ** 0.5
    
    def magnitude(self) -> float:
        return (self.x**2 + self.y**2 + self.z**2) ** 0.5

    def __mul__(self, other: float) -> 'Float3':
        return Float3(self.x * other, self.y * other, self.z * other)
    
    def __rmul__(self, other: float) -> 'Float3':
        return self.__mul__(other)
    
    def __add__(self, other: 'Float3') -> 'Float3':
        return Float3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other: 'Float3') -> 'Float3':
        return Float3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __truediv__(self, other: float) -> 'Float3':
        return Float3(self.x / other, self.y / other, self.z / other)

    def __rtruediv__(self, other: float) -> 'Float3':
        return Float3(other / self.x, other / self.y, other / self.z)

    def __str__(self):
        return f"Float3({self.x}, {self.y}, {self.z})"

    @property
    def r(self) -> float: return self.x
        
    @r.setter
    def r(self, value: float) -> None: self.x = value

    @property
    def g(self) -> float: return self.y

    @g.setter
    def g(self, value: float) -> None: self.y = value

    @property
    def b(self) -> float: return self.z

    @b.setter
    def b(self, value: float) -> None: self.z = value

    @property
    def color(self) -> tuple[float, float, float]:  
        return self.r, self.g, self.b

    def __setattr__(self, name, value):
        if name == 'on_changed':
            super().__setattr__(name, value)
            return

        if name in ['x', 'y', 'z', 'r', 'g', 'b']:
            super().__setattr__(name, value)
        
        if isinstance(value, (Float3)):
            if 'x' in name:
                self.x = value.x
            if 'y' in name:
                self.y = value.y
            if 'z' in name:
                self.z = value.z

            if 'r' in name:
                self.x = value.x
            if 'g' in name:
                self.y = value.y
            if 'b' in name:
                self.z = value.z

        if 'on_changed' in self.__dict__ and self.on_changed != None:
            self.on_changed()
