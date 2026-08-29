from pro import *

# exercises the row-vector matrix path in op_rectangle and op_translate
@rule
def Begin():
    extrude(5, top >> Top(), side >> Side())

@rule
def Top():
    rectangle(4, 3, Inner())

@rule
def Inner():
    translate(0, 0, 1)

@rule
def Side():
    color("#334455")
