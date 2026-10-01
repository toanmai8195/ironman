// updater: mỗi 1/RATE_PER_SEC giây cập nhật trạng thái của một đơn hàng ngẫu nhiên trong Postgres,
// để có luồng thay đổi liên tục cho Debezium/Flink.
package main

import (
	"context"
	"log/slog"
	"math/rand/v2"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"com.tm/ironman/com/tm/debezium/updater/internal/status"
)

func main() {
	log := slog.New(slog.NewTextHandler(os.Stdout, nil))
	if err := run(log); err != nil {
		log.Error("dừng do lỗi", "err", err)
		os.Exit(1)
	}
}

func run(log *slog.Logger) error {
	dsn := env("PG_DSN", "postgres://ironman:ironman@localhost:5434/ironman")
	rate := envInt("RATE_PER_SEC", 1)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return err
	}
	defer pool.Close()

	rng := rand.New(rand.NewPCG(uint64(time.Now().UnixNano()), 1))
	tick := time.NewTicker(time.Second / time.Duration(rate))
	defer tick.Stop()

	log.Info("update", "ratePerSec", rate)
	var updated int64
	for {
		select {
		case <-ctx.Done():
			log.Info("dừng", "updated", updated)
			return nil
		case <-tick.C:
			id, from, to, err := updateOne(ctx, pool, rng)
			if err != nil {
				// Postgres chưa sẵn sàng hoặc bảng rỗng: báo rồi thử lại ở nhịp sau, không thoát
				log.Warn("update lỗi", "err", err)
				continue
			}
			updated++
			log.Info("update", "orderId", id, "from", from, "to", to, "total", updated)
		}
	}
}

// updateOne đổi trạng thái của một đơn ngẫu nhiên trong một câu lệnh; trả về dòng bị đổi.
func updateOne(ctx context.Context, pool *pgxpool.Pool, rng *rand.Rand) (id int64, from, to string, err error) {
	if err = pool.QueryRow(ctx, `SELECT id, status FROM orders ORDER BY random() LIMIT 1`).Scan(&id, &from); err != nil {
		return 0, "", "", err
	}
	to = status.Next(from, rng)
	_, err = pool.Exec(ctx, `UPDATE orders SET status = $1 WHERE id = $2`, to, id)
	return id, from, to, err
}

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func envInt(k string, def int) int {
	if v := os.Getenv(k); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return def
}
