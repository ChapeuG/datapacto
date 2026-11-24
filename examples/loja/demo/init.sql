-- Banco de origem da demonstração: as tabelas da ddl.sql com dados de ontem (a carga diária lê D-1).
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

-- Dados fictícios. Os CPFs são números inventados, sem dígito verificador válido.
INSERT INTO public.cliente (id, name, email, document, city, created_at)
SELECT i,
       'Cliente ' || i,
       'cliente' || i || '@exemplo.com',
       lpad((11111111100 + i)::text, 11, '0'),
       (ARRAY['Recife', 'Curitiba', 'Belém', 'Goiânia', 'Natal'])[1 + i % 5],
       date_trunc('day', now() - interval '1 day') + (i * interval '7 minutes')
FROM generate_series(1, 50) AS i;

INSERT INTO public.pedido (id, customer_id, status, total_amount, created_at)
SELECT i,
       1 + i % 50,
       (ARRAY['ABERTO', 'PAGO', 'PAGO', 'CANCELADO'])[1 + i % 4],
       round((20 + (i * 37) % 480)::numeric + 0.90, 2),
       date_trunc('day', now() - interval '1 day') + (i * interval '3 minutes')
FROM generate_series(1, 200) AS i;
