// Package config đọc cấu hình cdc-consumer từ biến môi trường.
package config

import (
	"fmt"
	"os"
	"strings"
)

type Config struct {
	Brokers []string
	Topics  []string
	Group   string
}

// Load đọc env, có mặc định để chạy local từ host (Kafka listener HOST).
func Load() (Config, error) {
	cfg := Config{
		Brokers: split(get("KAFKA_BROKERS", "localhost:39092")),
		Topics:  split(get("KAFKA_TOPICS", "ironman.public.customers,ironman.public.orders")),
		Group:   get("KAFKA_GROUP", "ironman-cdc-consumer"),
	}
	if len(cfg.Brokers) == 0 || len(cfg.Topics) == 0 {
		return Config{}, fmt.Errorf("KAFKA_BROKERS và KAFKA_TOPICS không được rỗng")
	}
	return cfg, nil
}

func get(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func split(s string) []string {
	var out []string
	for _, p := range strings.Split(s, ",") {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	return out
}
