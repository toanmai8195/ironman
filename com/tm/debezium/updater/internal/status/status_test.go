package status

import (
	"math/rand/v2"
	"testing"
)

func TestNextAlwaysDiffers(t *testing.T) {
	rng := rand.New(rand.NewPCG(1, 2))
	seen := map[string]bool{}
	for i := 0; i < 500; i++ {
		for _, cur := range append([]string{"UNKNOWN"}, all...) {
			n := Next(cur, rng)
			if n == cur {
				t.Fatalf("Next(%q) trả về chính nó", cur)
			}
			seen[n] = true
		}
	}
	if len(seen) != len(all) {
		t.Fatalf("không phủ hết các trạng thái: %v", seen)
	}
}
