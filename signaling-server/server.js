// signaling-server/server.js
const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const crypto = require('crypto');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    }
});

class EphemeralSignalingServer {
    constructor() {
        this.rooms = new Map();
        this.userSockets = new Map();
        this.turnCredentials = this.generateTurnCredentials();
        
        // Auto-cleanup every 30 minutes
        setInterval(() => this.cleanupStaleRooms(), 30 * 60 * 1000);
        
        // Emergency cleanup on shutdown
        process.on('SIGTERM', () => this.emergencyCleanup());
        process.on('SIGINT', () => this.emergencyCleanup());
    }
    
    generateTurnCredentials() {
        const secret = process.env.TURN_SECRET || crypto.randomBytes(32).toString('hex');
        const username = crypto.randomBytes(16).toString('hex');
        const ttl = Math.floor(Date.now() / 1000) + 3600; // 1 hour
        
        const hmac = crypto.createHmac('sha1', secret);
        hmac.update(`${ttl}:${username}`);
        const password = hmac.digest('base64');
        
        return {
            username: `${ttl}:${username}`,
            credential: password,
            urls: [
                'turn:turn-server:3478?transport=udp',
                'turn:turn-server:3478?transport=tcp'
            ]
        };
    }
    
    handleConnection(socket) {
        console.log(`User connected: ${socket.id}`);
        
        // Send TURN credentials
        socket.emit('turn-credentials', this.turnCredentials);
        
        socket.on('join-room', (data) => {
            this.handleJoinRoom(socket, data);
        });
        
        socket.on('leave-room', () => {
            this.handleLeaveRoom(socket);
        });
        
        socket.on('webrtc-offer', (data) => {
            this.relayWebRTCMessage(socket, 'webrtc-offer', data);
        });
        
        socket.on('webrtc-answer', (data) => {
            this.relayWebRTCMessage(socket, 'webrtc-answer', data);
        });
        
        socket.on('webrtc-ice-candidate', (data) => {
            this.relayWebRTCMessage(socket, 'webrtc-ice-candidate', data);
        });
        
        socket.on('request-approval', (data) => {
            this.handleApprovalRequest(socket, data);
        });
        
        socket.on('approval-response', (data) => {
            this.handleApprovalResponse(socket, data);
        });
        
        socket.on('disconnect', () => {
            this.handleDisconnect(socket);
        });
    }
    
    handleJoinRoom(socket, data) {
        const { roomId, userId, userName } = data;
        
        if (!this.rooms.has(roomId)) {
            this.rooms.set(roomId, {
                participants: new Set(),
                createdAt: Date.now(),
                lastActivity: Date.now()
            });
        }
        
        const room = this.rooms.get(roomId);
        room.participants.add(socket.id);
        room.lastActivity = Date.now();
        
        this.userSockets.set(socket.id, {
            roomId,
            userId,
            userName
        });
        
        socket.join(roomId);
        socket.to(roomId).emit('user-joined', {
            userId,
            userName,
            socketId: socket.id
        });
        
        // Send current participants to new user
        const participants = Array.from(room.participants)
            .filter(id => id !== socket.id)
            .map(id => this.userSockets.get(id))
            .filter(Boolean);
            
        socket.emit('room-participants', participants);
    }
    
    handleLeaveRoom(socket) {
        const userInfo = this.userSockets.get(socket.id);
        if (!userInfo) return;
        
        const { roomId } = userInfo;
        const room = this.rooms.get(roomId);
        
        if (room) {
            room.participants.delete(socket.id);
            socket.to(roomId).emit('user-left', {
                socketId: socket.id,
                userId: userInfo.userId
            });
            
            // Clean room if empty
            if (room.participants.size === 0) {
                this.rooms.delete(roomId);
            }
        }
        
        socket.leave(roomId);
        this.userSockets.delete(socket.id);
    }
    
    relayWebRTCMessage(socket, event, data) {
        const userInfo = this.userSockets.get(socket.id);
        if (!userInfo) return;
        
        const { roomId } = userInfo;
        socket.to(roomId).emit(event, {
            ...data,
            fromSocket: socket.id
        });
    }
    
    handleApprovalRequest(socket, data) {
        const userInfo = this.userSockets.get(socket.id);
        if (!userInfo) return;
        
        const { roomId } = userInfo;
        socket.to(roomId).emit('approval-request', {
            requesterId: socket.id,
            requesterName: userInfo.userName,
            ...data
        });
    }
    
    handleApprovalResponse(socket, data) {
        const userInfo = this.userSockets.get(socket.id);
        if (!userInfo) return;
        
        const { approved, requesterId } = data;
        
        if (approved) {
            io.to(requesterId).emit('approval-granted', {
                approverId: socket.id,
                approverName: userInfo.userName
            });
        } else {
            io.to(requesterId).emit('approval-denied', {
                deniedBy: userInfo.userName
            });
        }
    }
    
    handleDisconnect(socket) {
        console.log(`User disconnected: ${socket.id}`);
        this.handleLeaveRoom(socket);
    }
    
    cleanupStaleRooms() {
        const now = Date.now();
        const staleTimeout = 30 * 60 * 1000; // 30 minutes
        
        for (const [roomId, room] of this.rooms.entries()) {
            if (now - room.lastActivity > staleTimeout) {
                // Notify participants and clean up
                for (const socketId of room.participants) {
                    const socket = io.sockets.sockets.get(socketId);
                    if (socket) {
                        socket.emit('room-expired');
                        socket.disconnect();
                    }
                }
                this.rooms.delete(roomId);
                console.log(`Cleaned up stale room: ${roomId}`);
            }
        }
    }
    
    emergencyCleanup() {
        console.log('Emergency cleanup initiated...');
        this.rooms.clear();
        this.userSockets.clear();
        process.exit(0);
    }
}

const signalingServer = new EphemeralSignalingServer();

io.on('connection', (socket) => {
    signalingServer.handleConnection(socket);
});

const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
    console.log(`Ephemeral Signaling Server running on port ${PORT}`);
});
