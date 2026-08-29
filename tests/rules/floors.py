from pro import *

@rule
def Begin():
    extrude(9, top >> Roof(), side >> Facade())

@rule
def Facade():
    split(y, flt(3) >> Floor(), flt(3) >> Floor())

@rule
def Floor():
    split(x, flt(2) >> Wall(), flt(3) >> Window())

@rule
def Wall():
    color("#cccccc")

@rule
def Window():
    texture("wall.png", 2, 3)

@rule
def Roof():
    color("#553322")
