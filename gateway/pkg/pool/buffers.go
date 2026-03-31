package pool

import (
	"bytes"
	"sync"
)

const maxBufferSize = 1 << 20 // 1MB

var bufferPool = sync.Pool{
	New: func() interface{} {
		return new(bytes.Buffer)
	},
}

func GetBuffer() *bytes.Buffer {
	buf := bufferPool.Get().(*bytes.Buffer)
	buf.Reset()
	return buf
}

func PutBuffer(buf *bytes.Buffer) {
	if buf.Cap() > maxBufferSize {
		return
	}
	bufferPool.Put(buf)
}

var bytesPool = sync.Pool{
	New: func() interface{} {
		b := make([]byte, 0, 4096)
		return &b
	},
}

func GetBytes() *[]byte {
	bp := bytesPool.Get().(*[]byte)
	*bp = (*bp)[:0]
	return bp
}

func PutBytes(bp *[]byte) {
	if cap(*bp) > maxBufferSize {
		return
	}
	bytesPool.Put(bp)
}
