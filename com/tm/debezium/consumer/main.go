// cdc-consumer: đọc event CDC (Postgres ──Debezium──► Kafka) và in log.
package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"com.tm/ironman/com/tm/debezium/consumer/internal/config"
	"com.tm/ironman/com/tm/debezium/consumer/internal/consume"
)

func main() {
	log := slog.New(slog.NewTextHandler(os.Stdout, nil))
	if err := run(log); err != nil {
		log.Error("dừng do lỗi", "err", err)
		os.Exit(1)
	}
}

func run(log *slog.Logger) error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	log.Info("consume", "brokers", cfg.Brokers, "topics", cfg.Topics, "group", cfg.Group)
	return consume.Run(ctx, cfg, log)
}
