from pro import *

height = param(10)

@rule
def Begin():
    extrude(height, top >> Roof(), side >> Facade())

@rule
def Facade():
    color("#ff0000")

@rule
def Roof():
    color("#00ff00")
