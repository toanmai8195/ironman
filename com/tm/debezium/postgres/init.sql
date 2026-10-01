-- Schema nguồn cho thử nghiệm CDC. Chạy tự động lần đầu khởi tạo volume (docker-entrypoint-initdb.d).
CREATE TABLE public.customers (
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT        NOT NULL,
    email      TEXT        NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.orders (
    id          BIGSERIAL PRIMARY KEY,
    customer_id BIGINT         NOT NULL REFERENCES public.customers (id),
    amount      NUMERIC(12, 2) NOT NULL,
    status      TEXT           NOT NULL DEFAULT 'NEW',
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT now()
);

INSERT INTO public.customers (name, email) VALUES
    ('An', 'an@example.com'),
    ('Binh', 'binh@example.com');

INSERT INTO public.orders (customer_id, amount) VALUES (1, 150000.00), (2, 99000.50);
