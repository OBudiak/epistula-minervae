variabilis integer Value <- 100.
nuntia structuram Box <<
    variabilis integer Value <- 10;
    nuntia edictum Local quo cape integer Value remitteque integer <<
        reditus Value!
    >>;
    nuntia edictum Field quo cape nihil remitteque integer <<
        reditus Value!
    >>;
>>.
variabilis b <- Box cape nihil.
Scribe b.Local(1), ",", b.Field(nihil), ",", Value, "/linea".
