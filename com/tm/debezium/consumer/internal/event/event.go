// Package event parse envelope CDC của Debezium (JSON, schemas.enable=false).
package event

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
)

// ErrTombstone: message value rỗng (tombstone), không mang thay đổi nào.
var ErrTombstone = errors.New("tombstone")

var opNames = map[string]string{
	"c": "create",
	"u": "update",
	"d": "delete",
	"r": "snapshot",
	"t": "truncate",
}

type Event struct {
	Topic     string         `json:"topic"`
	Partition int32          `json:"partition"`
	Offset    int64          `json:"offset"`
	Table     string         `json:"table"`
	Op        string         `json:"op"`
	OpName    string         `json:"opName"`
	TsMs      int64          `json:"tsMs"`
	LSN       int64          `json:"lsn"`
	Before    map[string]any `json:"before,omitempty"`
	After     map[string]any `json:"after,omitempty"`
}

type envelope struct {
	Before map[string]any `json:"before"`
	After  map[string]any `json:"after"`
	Op     string         `json:"op"`
	TsMs   int64          `json:"ts_ms"`
	Source struct {
		Schema string `json:"schema"`
		Table  string `json:"table"`
		LSN    int64  `json:"lsn"`
	} `json:"source"`
}

// Parse chuyển value của một message Kafka thành Event.
func Parse(topic string, partition int32, offset int64, value []byte) (Event, error) {
	if len(bytes.TrimSpace(value)) == 0 {
		return Event{}, ErrTombstone
	}
	var env envelope
	dec := json.NewDecoder(bytes.NewReader(value))
	dec.UseNumber() // giữ nguyên số lớn, không ép float64
	if err := dec.Decode(&env); err != nil {
		return Event{}, fmt.Errorf("parse envelope %s[%d]@%d: %w", topic, partition, offset, err)
	}
	if env.Op == "" {
		return Event{}, fmt.Errorf("envelope %s[%d]@%d thiếu op", topic, partition, offset)
	}
	name, ok := opNames[env.Op]
	if !ok {
		name = env.Op
	}
	return Event{
		Topic:     topic,
		Partition: partition,
		Offset:    offset,
		Table:     env.Source.Schema + "." + env.Source.Table,
		Op:        env.Op,
		OpName:    name,
		TsMs:      env.TsMs,
		LSN:       env.Source.LSN,
		Before:    env.Before,
		After:     env.After,
	}, nil
}
