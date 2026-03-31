package dbutil

import (
	"context"
	"fmt"
	"time"

	"gorm.io/gorm"
)

// PartitionConfig defines a table partitioning strategy.
type PartitionConfig struct {
	Table       string
	Column      string
	Type        string // RANGE, LIST, HASH
	Partitions  []PartitionDef
}

type PartitionDef struct {
	Name      string
	LessThan  string // for RANGE partitions
}

// CreateRangePartitions applies RANGE partitioning to an existing table.
// WARNING: This is a destructive DDL operation. Run during maintenance windows.
func CreateRangePartitions(ctx context.Context, db *gorm.DB, cfg PartitionConfig) error {
	if len(cfg.Partitions) == 0 {
		return fmt.Errorf("no partitions defined")
	}

	sql := fmt.Sprintf("ALTER TABLE %s PARTITION BY RANGE (%s) (\n", cfg.Table, cfg.Column)
	for i, p := range cfg.Partitions {
		sql += fmt.Sprintf("  PARTITION %s VALUES LESS THAN (%s)", p.Name, p.LessThan)
		if i < len(cfg.Partitions)-1 {
			sql += ",\n"
		} else {
			sql += "\n"
		}
	}
	sql += ")"

	return db.WithContext(ctx).Exec(sql).Error
}

// AddPartition adds a new partition to an already-partitioned table (before MAXVALUE).
func AddPartition(ctx context.Context, db *gorm.DB, table, partName, lessThan string) error {
	sql := fmt.Sprintf(
		"ALTER TABLE %s REORGANIZE PARTITION pmax INTO (PARTITION %s VALUES LESS THAN (%s), PARTITION pmax VALUES LESS THAN MAXVALUE)",
		table, partName, lessThan,
	)
	return db.WithContext(ctx).Exec(sql).Error
}

// DropPartition drops an old partition (archiving data permanently).
func DropPartition(ctx context.Context, db *gorm.DB, table, partName string) error {
	sql := fmt.Sprintf("ALTER TABLE %s DROP PARTITION %s", table, partName)
	return db.WithContext(ctx).Exec(sql).Error
}

// GetPartitionInfo retrieves partition metadata for a table.
func GetPartitionInfo(ctx context.Context, db *gorm.DB, table string) ([]map[string]interface{}, error) {
	var results []map[string]interface{}
	err := db.WithContext(ctx).Raw(
		"SELECT PARTITION_NAME, PARTITION_ORDINAL_POSITION, TABLE_ROWS, DATA_LENGTH, PARTITION_DESCRIPTION "+
			"FROM INFORMATION_SCHEMA.PARTITIONS WHERE TABLE_NAME = ? AND PARTITION_NAME IS NOT NULL "+
			"ORDER BY PARTITION_ORDINAL_POSITION",
		table,
	).Scan(&results).Error
	return results, err
}

// --- Pre-built partition configs for the project ---

func ChapterVersionsPartitionConfig() PartitionConfig {
	return PartitionConfig{
		Table:  "chapter_versions",
		Column: "id",
		Type:   "RANGE",
		Partitions: []PartitionDef{
			{Name: "p0", LessThan: "5000000"},
			{Name: "p1", LessThan: "10000000"},
			{Name: "p2", LessThan: "15000000"},
			{Name: "p3", LessThan: "20000000"},
			{Name: "pmax", LessThan: "MAXVALUE"},
		},
	}
}

func PaymentOrdersPartitionConfig() PartitionConfig {
	return PartitionConfig{
		Table:  "payment_orders",
		Column: "UNIX_TIMESTAMP(created_at)",
		Type:   "RANGE",
		Partitions: func() []PartitionDef {
			var defs []PartitionDef
			start := 2025
			for y := start; y <= start+5; y++ {
				defs = append(defs, PartitionDef{
					Name:     fmt.Sprintf("p%d", y),
					LessThan: fmt.Sprintf("UNIX_TIMESTAMP('%d-01-01')", y+1),
				})
			}
			defs = append(defs, PartitionDef{Name: "pmax", LessThan: "MAXVALUE"})
			return defs
		}(),
	}
}

func WritingArchivesPartitionConfig() PartitionConfig {
	now := time.Now()
	year := now.Year()
	return PartitionConfig{
		Table:  "writing_archives",
		Column: "UNIX_TIMESTAMP(created_at)",
		Type:   "RANGE",
		Partitions: []PartitionDef{
			{Name: fmt.Sprintf("p%d", year), LessThan: fmt.Sprintf("UNIX_TIMESTAMP('%d-01-01')", year+1)},
			{Name: fmt.Sprintf("p%d", year+1), LessThan: fmt.Sprintf("UNIX_TIMESTAMP('%d-01-01')", year+2)},
			{Name: "pmax", LessThan: "MAXVALUE"},
		},
	}
}
