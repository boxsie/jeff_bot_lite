export class BrowserClient {
    constructor(address, port) {
        this._address = address;
        this._port = port;
        this._client = null;
    }

    connect(onmessage, onopen) {
        this._client = new WebSocket(`wss://${this._address}/`);
        this._client.onopen = (event) => onopen ? onopen(event.data) : this._onHandshake(event);
        this._client.onerror = (event) => this._onError(event);
        this._client.onclose = (event) => this._onClose(event);
        this._client.onmessage = (event) => onmessage ? onmessage(event.data) : this._onMessage(event);
    }

    sendMessage(message) {
        this._client.send(message);
    }

    _onHandshake(event) {
        console.log('JS client connected');
    }

    _onMessage(event) {
        console.log(`Received: '${event.data}`);
    }

    _onClose(event) {
        console.log('JS connection closed');
    }

    _onError(event) {
        console.log(`JS connection error: ${event}`);
    }
}