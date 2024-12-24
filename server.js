const express = require('express')
const bodyParser = require("body-parser")
const Docker = require("docker")

const app = express()
const docker = new Docker()

app.use(bodyParser.json())

app.post('/start-container', async(req, res)=>{
    const {imageName, port} = req.body

    try{
        await docker.pull(imageName, {})
        const container = await docker.createContainer({
            Image: imageName,
            ExposedPorts: {"8888/tcp":{}},
            HostConfig:{
                PortBindings:{"8888/tcp": [{HostPort: `${port}`}]},
                Runtime:'nvidia'
            }
        })

        await container.start()
        // Using domain instead of IP since traffic will come through Cloudflare
        res.json({
            message: "Container Started",
            link: `https://indiegpu.com:${port}`
        })

    }catch(error){
        console.error(error)
        res.status(500).json({error: "Failed to start container"})
    }
})

app.post("/stop-container", async(req, res)=>{
    const {containerId} = req.body
    try{
        const container = docker.getContainer(containerId)
        await container.stop()
        res.json({message: "Container stopped"})
    }catch(error){
        console.error(error)
        res.status(500).json({error:"Failed to stop container"})
    }
})

const PORT = 8000;
app.listen(PORT, '0.0.0.0', () => {
    console.log(`Backend running on http://localhost:${PORT}`);
});