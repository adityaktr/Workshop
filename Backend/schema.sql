CREATE TABLE IF NOT EXISTS appliances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    wattage INTEGER NOT NULL CHECK (wattage > 0),
    priority INTEGER NOT NULL CHECK (priority >= 1),
    status TEXT NOT NULL CHECK (status IN ('running', 'off', 'shed')) DEFAULT 'off'
);