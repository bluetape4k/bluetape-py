package main

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"os"
	"slices"

	"github.com/apache/fory/go/fory"
)

const (
	headerSize    = 20
	schemaID      = uint32(1112819289)
	schemaVersion = uint16(1)
	typeID        = uint32(1001)
)

var magic = [4]byte{'B', 'T', 'F', 'Y'}

type ConformanceRecord struct {
	RecordID int64   `fory:"id=1"`
	Name     string  `fory:"id=2"`
	Active   bool    `fory:"id=3"`
	Scores   []int32 `fory:"id=4"`
}

var expected = ConformanceRecord{
	RecordID: 7,
	Name:     "blue",
	Active:   true,
	Scores:   []int32{1, 2, 3},
}

func newFory() (*fory.Fory, error) {
	f := fory.New(
		fory.WithXlang(true),
		fory.WithTrackRef(false),
		fory.WithCompatible(false),
		fory.WithMaxDepth(64),
		fory.WithMaxTypeFields(256),
		fory.WithMaxTypeMetaBytes(4096),
		fory.WithMaxSchemaVersionsPerType(8),
		fory.WithMaxAverageSchemaVersionsPerType(2),
	)
	if err := f.RegisterStruct(ConformanceRecord{}, typeID); err != nil {
		return nil, err
	}
	return f, nil
}

func wrap(body []byte) []byte {
	result := make([]byte, headerSize+len(body))
	copy(result[:4], magic[:])
	result[4] = 1
	result[5] = 0
	binary.BigEndian.PutUint32(result[6:10], schemaID)
	binary.BigEndian.PutUint16(result[10:12], schemaVersion)
	binary.BigEndian.PutUint32(result[12:16], typeID)
	binary.BigEndian.PutUint32(result[16:20], uint32(len(body)))
	copy(result[20:], body)
	return result
}

func unwrap(data []byte) ([]byte, error) {
	if len(data) < headerSize || !bytes.Equal(data[:4], magic[:]) {
		return nil, errors.New("invalid bluetape Fory envelope")
	}
	if data[4] != 1 || data[5] != 0 {
		return nil, errors.New("unsupported bluetape Fory envelope")
	}
	if binary.BigEndian.Uint32(data[6:10]) != schemaID ||
		binary.BigEndian.Uint16(data[10:12]) != schemaVersion ||
		binary.BigEndian.Uint32(data[12:16]) != typeID {
		return nil, errors.New("bluetape Fory registration mismatch")
	}
	bodyLength := binary.BigEndian.Uint32(data[16:20])
	if bodyLength == 0 || uint64(bodyLength) != uint64(len(data)-headerSize) {
		return nil, errors.New("invalid bluetape Fory body length")
	}
	return data[headerSize:], nil
}

func generate(path string) error {
	f, err := newFory()
	if err != nil {
		return err
	}
	body, err := f.Serialize(&expected)
	if err != nil {
		return err
	}
	return os.WriteFile(path, wrap(bytes.Clone(body)), 0o644)
}

func verify(path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	body, err := unwrap(data)
	if err != nil {
		return err
	}
	f, err := newFory()
	if err != nil {
		return err
	}
	var result ConformanceRecord
	if err := f.Deserialize(body, &result); err != nil {
		return err
	}
	if result.RecordID != expected.RecordID || result.Name != expected.Name ||
		result.Active != expected.Active || !slices.Equal(result.Scores, expected.Scores) {
		return errors.New("Fory conformance value does not match the canonical record")
	}
	return nil
}

func main() {
	if len(os.Args) != 3 || (os.Args[1] != "generate" && os.Args[1] != "verify") {
		fmt.Fprintln(os.Stderr, "usage: fory-conformance generate|verify PATH")
		os.Exit(2)
	}
	var err error
	if os.Args[1] == "generate" {
		err = generate(os.Args[2])
	} else {
		err = verify(os.Args[2])
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
