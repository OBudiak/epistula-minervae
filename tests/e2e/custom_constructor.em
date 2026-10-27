nuntia structuram Nums <<
    immutabilis integer right;
    mutabilis integer left;
    immutabilis sententia message;
    nuntia edictum Nums quo cape integer First, integer Second, sententia Label <<
        message <- Label;
        left <- First;
        right <- Second;
    >>;
    nuntia edictum Later quo cape integer amount remitteque integer <<
        integer Result <- left + right + amount;
        reditus Result!
    >>;
>>.
variabilis nums <- novum Nums quo cape 3, 4, "lala".
Nums other <- novum Label <- "other", Second <- 9, First <- 8.
Nums third <- novum 6, 7, "third".
Scribe nums, "/linea", other, "/linea", nums > Later quo cape 2.
Scribe - "/linea".
Scribe third, "/linea".
