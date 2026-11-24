-- Loja fictícia: clientes e pedidos. Ponto de partida do exemplo (ver examples/README.md).
CREATE TABLE public.cliente (
    id          INTEGER      PRIMARY KEY,
    name        VARCHAR(120) NOT NULL,
    email       VARCHAR(160) NOT NULL,
    document    VARCHAR(14)  NOT NULL,
    city        VARCHAR(80),
    created_at  TIMESTAMP    NOT NULL
);

CREATE TABLE public.pedido (
    id           INTEGER       PRIMARY KEY,
    customer_id  INTEGER       NOT NULL REFERENCES cliente(id),
    status       VARCHAR(20)   NOT NULL,
    total_amount NUMERIC(12,2) NOT NULL,
    created_at   TIMESTAMP     NOT NULL
);
