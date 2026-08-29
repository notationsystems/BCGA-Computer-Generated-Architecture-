from pro import *

# two distinct uv layers; the second one has to be created on demand
@rule
def Begin():
    extrude(10, top >> Roof(), side >> Facade())

@rule
def Facade():
    texture("wall.png", 4, 3, layer="second")

@rule
def Roof():
    color("#00ff00")
