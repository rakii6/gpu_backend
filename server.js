const express = require('express');
const bodyParser = require('body-parser');

const app = express();
const PORT = 3000;

// Middleware
app.use(bodyParser.json());

// Endpoints
app.get('/status', (req, res) => {
    res.json({
        message: 'Server is running',
        gpuStatus: 'Idle', //needs to be fetched later on
    });
});

app.post('/task', (req, res) => {
    const { task } = req.body;
    // Process the task (placeholder)
    const taskId = Date.now(); //   ID
    res.json({
        message: 'Task received',
        taskId,
    });
});

app.get('/task/:id', (req, res) => {
    const { id } = req.params;
    // Placeholder for task progress
    res.json({
        taskId: id,
        status: 'Processing', // replace with real status later
    });
});

// Start the server
app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});
