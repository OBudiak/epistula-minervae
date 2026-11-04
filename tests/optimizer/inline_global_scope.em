integer Shared <- 5.
nuntia edictum Capture quo cape nihil remitteque integer <<
    reditus Shared!
>>.
nuntia edictum Caller quo cape nihil remitteque integer <<
    integer Shared <- 9;
    integer Result <- Capture(nihil);
    reditus Result!
>>.
Scribe Caller(nihil), "/linea".
