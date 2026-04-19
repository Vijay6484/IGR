const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(cors());

const INDEX_DIR = path.join(__dirname, '..', 'Scripts', 'index_output');

app.get('/api/locations', (req, res) => {
    const locationsPath = path.join(__dirname, 'locations.json');
    if (!fs.existsSync(locationsPath)) {
        return res.status(404).json({ error: "Locations file not found" });
    }
    try {
        const locationsData = fs.readFileSync(locationsPath, 'utf8');
        res.json(JSON.parse(locationsData));
    } catch (e) {
        res.status(500).json({ error: "Failed to read locations" });
    }
});

app.get('/api/search', (req, res) => {
    const { district, taluka, village, query } = req.query;

    if (!district || !taluka || !village || !query) {
        return res.status(400).json({ error: "Missing required parameters" });
    }

    if (!/^\d+$/.test(query)) {
        return res.status(400).json({ error: "Query must be numeric" });
    }

    const filePath = path.join(INDEX_DIR, district, taluka, village, 'data.json');
    if (!fs.existsSync(filePath)) {
        return res.status(404).json({ error: "Data file not found for the selected location" });
    }

    try {
        const fileData = fs.readFileSync(filePath, 'utf8');
        const records = JSON.parse(fileData);
        const results = [];

        for (const record of records) {
            if (record.property_numbers && Array.isArray(record.property_numbers)) {
                for (const prop of record.property_numbers) {
                    if (prop.value === String(query)) {
                        results.push(record);
                        break; // Found matching property number in this doc
                    }
                }
            }
        }

        res.json({ count: results.length, results });
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: "Internal server error reading data file" });
    }
});

const PORT = 8000;
app.listen(PORT, () => {
    console.log(`Node.js Backend listening on port ${PORT}`);
});
