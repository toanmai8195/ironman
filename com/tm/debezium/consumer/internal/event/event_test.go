package event

import (
	"errors"
	"testing"
)

func TestParse(t *testing.T) {
	tests := []struct {
		name      string
		value     string
		wantErr   error
		wantAny   bool
		wantTable string
		wantOp    string
	}{
		{
			name:      "create",
			value:     `{"before":null,"after":{"id":1,"name":"An"},"source":{"schema":"public","table":"customers","lsn":42},"op":"c","ts_ms":1700000000000}`,
			wantTable: "public.customers",
			wantOp:    "create",
		},
		{
			name:      "delete",
			value:     `{"before":{"id":1},"after":null,"source":{"schema":"public","table":"orders","lsn":43},"op":"d","ts_ms":1}`,
			wantTable: "public.orders",
			wantOp:    "delete",
		},
		{name: "tombstone", value: ``, wantErr: ErrTombstone},
		{name: "json hỏng", value: `{`, wantAny: true},
		{name: "thiếu op", value: `{"source":{}}`, wantAny: true},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			ev, err := Parse("t", 0, 7, []byte(tc.value))
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("err = %v, want %v", err, tc.wantErr)
				}
				return
			}
			if tc.wantAny {
				if err == nil {
					t.Fatal("muốn lỗi nhưng không có")
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if ev.Table != tc.wantTable || ev.OpName != tc.wantOp || ev.Offset != 7 {
				t.Fatalf("got %+v", ev)
			}
		})
	}
}
