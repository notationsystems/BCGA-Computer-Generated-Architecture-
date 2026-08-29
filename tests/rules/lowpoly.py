from pro import *

height = param(9)

@rule
def Begin():
    extrude(height, top >> Roof(), side >> Facade())

@rule
def Facade():
    color("#888888")

@rule
def Roof():
    color("#553322")
