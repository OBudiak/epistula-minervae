nuntia structuram Box <<
    mutabilis duplex value;
>>.
nuntia in filo Worker quo cape Box Item <<
    Item.value <- 9;
>>.
Box Item <- novum 1.
filum Task <- incipe Worker(Item).
exspecta Task.
Scribe Item.value, "/linea".
