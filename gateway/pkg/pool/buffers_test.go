package pool

import (
	"testing"
)

func TestGetPutBuffer(t *testing.T) {
	buf := GetBuffer()
	if buf == nil {
		t.Fatal("GetBuffer returned nil")
	}
	buf.WriteString("hello world")
	if buf.Len() != 11 {
		t.Fatalf("expected length 11, got %d", buf.Len())
	}
	PutBuffer(buf)

	// After put, buffer should be reset
	buf2 := GetBuffer()
	if buf2.Len() != 0 {
		t.Fatalf("expected reset buffer, got length %d", buf2.Len())
	}
	PutBuffer(buf2)
}

func TestGetPutBytes(t *testing.T) {
	bp := GetBytes()
	if bp == nil {
		t.Fatal("GetBytes returned nil")
	}
	*bp = append(*bp, "hello"...)
	if len(*bp) != 5 {
		t.Fatalf("expected length 5, got %d", len(*bp))
	}
	PutBytes(bp)

	bp2 := GetBytes()
	if len(*bp2) != 0 {
		t.Fatalf("expected reset bytes, got length %d", len(*bp2))
	}
	PutBytes(bp2)
}

func BenchmarkBufferPool(b *testing.B) {
	b.ReportAllocs()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			buf := GetBuffer()
			buf.WriteString("benchmark test data for sync.Pool performance validation")
			PutBuffer(buf)
		}
	})
}

func BenchmarkBufferNoPool(b *testing.B) {
	b.ReportAllocs()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			buf := make([]byte, 0, 256)
			buf = append(buf, "benchmark test data for sync.Pool performance validation"...)
			_ = buf
		}
	})
}

func BenchmarkBytesPool(b *testing.B) {
	b.ReportAllocs()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			bp := GetBytes()
			*bp = append(*bp, "benchmark data payload for pool test"...)
			PutBytes(bp)
		}
	})
}
