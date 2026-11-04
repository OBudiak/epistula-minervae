duplex Total <- 0.
nuntia finite 1 ad 3 quo index Row <<
    nuntia finite 1 ad 2 quo index Col <<
        duplex Value <- Row * Col;
        Total <- Total + Value;
    >>;
>>.
Scribe Total, "/linea".
