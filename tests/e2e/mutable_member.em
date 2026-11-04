nuntia structuram Counter <<
    mutabilis integer value <- 0;
    nuntia edictum Inc quo cape integer amount remitteque nihil <<
        value <- value + amount;
        reditus nihil!
    >>;
    nuntia edictum Get quo cape nihil remitteque integer <<
        reditus value!
    >>;
>>.
variabilis c <- novum Counter quo cape nihil.
c.Inc(5).
Scribe c > Get(nihil), "/linea".
