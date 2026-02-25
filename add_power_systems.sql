-- Migration: Add PowerSystem and PowerLevel tables
-- Description: Creates the tables for storing power systems and relates them to BlueprintCharacters.

CREATE TABLE power_systems (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES novel_projects (id) ON DELETE CASCADE
);

CREATE TABLE power_levels (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    power_system_id INT NOT NULL,
    level INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    abilities TEXT,
    limitations TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(power_system_id) REFERENCES power_systems (id) ON DELETE CASCADE
);

-- Add columns to blueprint_characters table and set up foreign keys for MySQL
ALTER TABLE blueprint_characters ADD COLUMN power_system_id INT NULL;
ALTER TABLE blueprint_characters ADD COLUMN current_power_level_id INT NULL;

ALTER TABLE blueprint_characters ADD CONSTRAINT fk_character_power_system FOREIGN KEY (power_system_id) REFERENCES power_systems(id) ON DELETE SET NULL;
ALTER TABLE blueprint_characters ADD CONSTRAINT fk_character_power_level FOREIGN KEY (current_power_level_id) REFERENCES power_levels(id) ON DELETE SET NULL;

CREATE INDEX idx_power_systems_project_id ON power_systems (project_id);
CREATE INDEX idx_power_levels_system_id ON power_levels (power_system_id);
