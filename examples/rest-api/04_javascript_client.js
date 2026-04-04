// JavaScript/Node.js client for planfile REST API
// 
// Run with: node 04_javascript_client.js

const BASE_URL = process.env.PLANFILE_URL || 'http://localhost:8000';

class PlanfileClient {
    constructor(baseUrl = BASE_URL) {
        this.baseUrl = baseUrl;
    }

    async request(method, path, body = null, queryParams = {}) {
        const url = new URL(path, this.baseUrl);
        
        // Add query params
        Object.entries(queryParams).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
                url.searchParams.append(key, value);
            }
        });

        const options = {
            method,
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        };

        if (body) {
            options.body = JSON.stringify(body);
        }

        const response = await fetch(url, options);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return response.json();
    }

    // Health check
    async health() {
        return this.request('GET', '/health');
    }

    // List tickets
    async listTickets({ sprint, status, priority } = {}) {
        return this.request('GET', '/tickets', null, { sprint, status, priority });
    }

    // Create ticket
    async createTicket({ title, description = '', priority = 'normal', sprint = 'current', labels = [] }) {
        return this.request('POST', '/tickets', { title, description, priority, sprint, labels });
    }

    // Get ticket
    async getTicket(ticketId) {
        return this.request('GET', `/tickets/${ticketId}`);
    }

    // Update ticket
    async updateTicket(ticketId, updates) {
        return this.request('PATCH', `/tickets/${ticketId}`, updates);
    }

    // Move ticket
    async moveTicket(ticketId, toSprint) {
        return this.request('POST', `/tickets/${ticketId}/move`, null, { to_sprint: toSprint });
    }

    // Delete ticket
    async deleteTicket(ticketId) {
        const url = new URL(`/tickets/${ticketId}`, this.baseUrl);
        const response = await fetch(url, { method: 'DELETE' });
        return response.ok;
    }
}

// Example usage
async function examples() {
    console.log('='.repeat(60));
    console.log('Planfile REST API - JavaScript Client Examples');
    console.log('='.repeat(60));
    console.log();

    const client = new PlanfileClient();

    try {
        // 1. Health check
        console.log('1. Health Check');
        const health = await client.health();
        console.log('   Server status:', health);
        console.log();

        // 2. Create ticket
        console.log('2. Create Ticket');
        const ticket = await client.createTicket({
            title: 'JS API Test: Frontend bug',
            description: 'Button not responding on mobile',
            priority: 'high',
            labels: ['bug', 'frontend', 'mobile']
        });
        console.log('   Created:', ticket.id);
        console.log();

        // 3. Get ticket
        console.log('3. Get Ticket');
        const fetched = await client.getTicket(ticket.id);
        console.log('   Title:', fetched.title);
        console.log();

        // 4. Update ticket
        console.log('4. Update Ticket');
        const updated = await client.updateTicket(ticket.id, {
            status: 'in_progress',
            assignee: 'js-developer'
        });
        console.log('   Status:', updated.status);
        console.log();

        // 5. List tickets
        console.log('5. List Tickets');
        const tickets = await client.listTickets({ sprint: 'current' });
        console.log('   Found:', tickets.length, 'tickets');
        console.log();

        // 6. Move ticket
        console.log('6. Move Ticket');
        const moved = await client.moveTicket(ticket.id, 'next-sprint');
        console.log('   Moved to:', moved.to);
        console.log();

        console.log('='.repeat(60));
        console.log('All JavaScript examples completed!');
        console.log('='.repeat(60));

    } catch (error) {
        console.error('Error:', error.message);
        console.log('\nMake sure the server is running:');
        console.log('  ./01_start_server.sh');
        process.exit(1);
    }
}

// Run if called directly
if (require.main === module) {
    examples();
}

module.exports = { PlanfileClient };
