# Narrowing for `is` conditionals

## `is None`

```py
def bool_instance() -> bool:
    return True

flag = bool_instance()
x = None if flag else 1

if x is None:
    reveal_type(x)  # revealed: None
else:
    reveal_type(x)  # revealed: Literal[1]

reveal_type(x)  # revealed: None | Literal[1]
```

## `is` for other types

```py
def bool_instance() -> bool:
    return True

flag = bool_instance()

class A: ...

x = A()
y = x if flag else None

if y is x:
    reveal_type(y)  # revealed: A
else:
    reveal_type(y)  # revealed: A | None

reveal_type(y)  # revealed: A | None
```

## `is` in chained comparisons

```py
def bool_instance() -> bool:
    return True

x_flag, y_flag = bool_instance(), bool_instance()
x = True if x_flag else False
y = True if y_flag else False

reveal_type(x)  # revealed: bool
reveal_type(y)  # revealed: bool

if y is x is False:  # Interpreted as `(y is x) and (x is False)`
    reveal_type(x)  # revealed: Literal[False]
    reveal_type(y)  # revealed: bool
else:
    # The negation of the clause above is (y is not x) or (x is not False)
    # So we can't narrow the type of x or y here, because each arm of the `or` could be true
    reveal_type(x)  # revealed: bool
    reveal_type(y)  # revealed: bool
```

## `is` in elif clause

```py
def bool_instance() -> bool:
    return True

x = None if bool_instance() else (1 if bool_instance() else True)

reveal_type(x)  # revealed: None | Literal[1] | Literal[True]
if x is None:
    reveal_type(x)  # revealed: None
elif x is True:
    reveal_type(x)  # revealed: Literal[True]
else:
    reveal_type(x)  # revealed: Literal[1]
```