// Package consume đọc topic CDC bằng Kafka consumer group, parse và in log.
package consume

import (
	"context"
	"errors"
	"fmt"
	"log/slog"

	"github.com/IBM/sarama"

	"com.tm/ironman/com/tm/debezium/consumer/internal/config"
	"com.tm/ironman/com/tm/debezium/consumer/internal/event"
)

type handler struct {
	log *slog.Logger
}

func (handler) Setup(sarama.ConsumerGroupSession) error   { return nil }
func (handler) Cleanup(sarama.ConsumerGroupSession) error { return nil }

func (h handler) ConsumeClaim(sess sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
	for {
		select {
		case msg, ok := <-claim.Messages():
			if !ok {
				return nil
			}
			ev, err := event.Parse(msg.Topic, msg.Partition, msg.Offset, msg.Value)
			switch {
			case errors.Is(err, event.ErrTombstone):
			case err != nil:
				h.log.Warn("bỏ qua message lỗi", "err", err)
			default:
				h.log.Info("cdc",
					"op", ev.OpName, "table", ev.Table,
					"topic", ev.Topic, "partition", ev.Partition, "offset", ev.Offset,
					"before", ev.Before, "after", ev.After)
			}
			sess.MarkMessage(msg, "")
		case <-sess.Context().Done():
			return nil
		}
	}
}

// Run chạy đến khi ctx bị huỷ; tự join lại group khi rebalance.
func Run(ctx context.Context, cfg config.Config, log *slog.Logger) error {
	sc := sarama.NewConfig()
	sc.Version = sarama.V3_6_0_0
	sc.Consumer.Offsets.Initial = sarama.OffsetOldest
	sc.Consumer.Return.Errors = true

	group, err := sarama.NewConsumerGroup(cfg.Brokers, cfg.Group, sc)
	if err != nil {
		return fmt.Errorf("tạo consumer group: %w", err)
	}
	defer group.Close()

	go func() {
		for err := range group.Errors() {
			log.Error("kafka", "err", err)
		}
	}()

	h := handler{log: log}
	for ctx.Err() == nil {
		if err := group.Consume(ctx, cfg.Topics, h); err != nil {
			if errors.Is(err, sarama.ErrClosedConsumerGroup) {
				return nil
			}
			return fmt.Errorf("consume: %w", err)
		}
	}
	return nil
}
