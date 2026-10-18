// Package status chọn trạng thái đơn hàng tiếp theo cho updater.
package status

import "math/rand/v2"

var all = []string{"NEW", "PAID", "SHIPPED", "DELIVERED", "CANCELLED"}

// Next trả về một trạng thái khác current, để mỗi UPDATE đều thực sự đổi giá trị (không đổi thì Postgres vẫn
// ghi WAL nhưng event CDC có before == after, khó quan sát).
func Next(current string, rng *rand.Rand) string {
	for {
		if s := all[rng.IntN(len(all))]; s != current {
			return s
		}
	}
}
