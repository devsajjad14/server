# E-commerce FastAPI Backend with PayPal Commerce Platform

This is a modern, production-ready FastAPI backend for e-commerce applications with integrated PayPal Commerce Platform payment processing.

## Features

- **PayPal Commerce Platform Integration**: Complete payment processing with PayPal
- **Modern FastAPI Architecture**: Async/await patterns, proper error handling, and validation
- **Comprehensive Logging**: Detailed logging for debugging and monitoring
- **Background Tasks**: Non-blocking operations for better performance
- **Webhook Support**: Real-time payment notifications from PayPal
- **CORS Configuration**: Ready for Next.js frontend integration
- **Environment Configuration**: Secure configuration management

## Project Structure

```
server/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── hello/                  # Example module
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── services.py
│   └── checkout/               # PayPal Commerce Platform integration
│       ├── __init__.py
│       ├── routes.py           # API endpoints
│       ├── schemas.py          # Pydantic models
│       └── services.py         # Business logic
├── config.py                   # Application configuration
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Activate virtual environment
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. PayPal Commerce Platform Setup

1. **Create PayPal Developer Account**:
   - Go to [PayPal Developer Portal](https://developer.paypal.com/)
   - Sign up for a developer account
   - Create a new app for your application

2. **Get API Credentials**:
   - In your PayPal app, get the Client ID and Client Secret
   - For testing, use Sandbox credentials
   - For production, use Live credentials

3. **Configure Environment Variables**:
   Create a `.env` file in the server directory:
   ```env
   # PayPal Commerce Platform Configuration
   PAYPAL_CLIENT_ID=your_paypal_client_id_here
   PAYPAL_CLIENT_SECRET=your_paypal_client_secret_here
   PAYPAL_MODE=sandbox  # Change to 'live' for production
   
   # Application Configuration
   APP_ENV=development
   DEBUG=true
   FRONTEND_URL=http://localhost:3000
   ```

### 3. Run the Server

```bash
# From the server directory
uvicorn app.main:app --reload --port 8000
```

The server will be available at `http://localhost:8000`

## API Endpoints

### Checkout Endpoints

#### POST `/checkout/process-paypal`
Process PayPal Commerce Platform checkout.

**Request Body**:
```json
{
  "order_id": "ORDER_123",
  "customer": {
    "email": "customer@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+1234567890"
  },
  "items": [
    {
      "product_id": "PROD_001",
      "name": "Product Name",
      "quantity": 2,
      "unit_price": "29.99",
      "currency": "USD",
      "description": "Product description"
    }
  ],
  "shipping_address": {
    "line1": "123 Main St",
    "city": "New York",
    "state": "NY",
    "postal_code": "10001",
    "country_code": "US"
  },
  "subtotal": "59.98",
  "tax_amount": "5.00",
  "shipping_amount": "5.99",
  "discount_amount": "0.00",
  "total_amount": "70.97",
  "currency": "USD",
  "payment_method": "paypal"
}
```

**Response**:
```json
{
  "success": true,
  "order_id": "ORDER_123",
  "paypal_order_id": "PAYPAL_ORDER_ID",
  "status": "created",
  "message": "PayPal order created successfully",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### POST `/checkout/capture-payment`
Capture PayPal payment for an approved order.

**Request Body**:
```json
{
  "payment_id": "PAYPAL_ORDER_ID",
  "order_id": "ORDER_123"
}
```

#### GET `/checkout/order/{paypal_order_id}`
Get PayPal order details.

#### POST `/checkout/webhook`
Handle PayPal webhook events (for production).

#### GET `/checkout/health`
Health check endpoint.

### Example Endpoints

#### GET `/hello`
Simple hello world endpoint.

## Frontend Integration

### Next.js Integration Example

```typescript
// Process PayPal checkout
const processPayPalCheckout = async (orderData: any) => {
  try {
    const response = await fetch('http://localhost:8000/checkout/process-paypal', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(orderData),
    });
    
    const result = await response.json();
    
    if (result.success) {
      // Handle successful order creation
      console.log('PayPal order created:', result.paypal_order_id);
      
      // Redirect to PayPal or handle payment flow
      // You can use PayPal JavaScript SDK here
    } else {
      // Handle error
      console.error('Checkout failed:', result.message);
    }
  } catch (error) {
    console.error('Error processing checkout:', error);
  }
};

// Capture payment
const capturePayment = async (paypalOrderId: string, orderId: string) => {
  try {
    const response = await fetch('http://localhost:8000/checkout/capture-payment', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        payment_id: paypalOrderId,
        order_id: orderId,
      }),
    });
    
    const result = await response.json();
    
    if (result.success) {
      // Payment captured successfully
      console.log('Payment captured:', result.capture_id);
      // Redirect to success page
      window.location.href = '/checkout/success';
    } else {
      // Handle capture error
      console.error('Payment capture failed:', result.message);
    }
  } catch (error) {
    console.error('Error capturing payment:', error);
  }
};
```

## PayPal Commerce Platform Features

### Supported Payment Methods
- PayPal Checkout
- PayPal Credit
- Venmo (US only)
- Local payment methods (varies by country)

### Payment Flow
1. **Order Creation**: Frontend sends order data to `/checkout/process-paypal`
2. **PayPal Order**: Backend creates PayPal order and returns order ID
3. **Payment Approval**: User approves payment on PayPal (stays on your site)
4. **Payment Capture**: Frontend calls `/checkout/capture-payment` to capture funds
5. **Success**: User redirected to success page

### Webhook Events
The system handles these PayPal webhook events:
- `PAYMENT.CAPTURE.COMPLETED`: Payment successfully captured
- `PAYMENT.CAPTURE.DENIED`: Payment denied
- `CHECKOUT.ORDER.APPROVED`: Order approved by customer

## Production Considerations

### Security
1. **Environment Variables**: Never commit `.env` files to version control
2. **Webhook Verification**: Implement proper webhook signature verification
3. **HTTPS**: Use HTTPS in production
4. **Input Validation**: All inputs are validated using Pydantic schemas

### Monitoring
1. **Logging**: Comprehensive logging for debugging
2. **Error Handling**: Proper error responses and logging
3. **Health Checks**: Health check endpoint for monitoring

### Database Integration
The current implementation includes placeholders for database operations. You should:
1. Add your database models
2. Implement order storage
3. Add payment status tracking
4. Implement webhook event storage

### PayPal Production Setup
1. **Live Credentials**: Switch to live PayPal credentials
2. **Webhook URL**: Configure webhook URL in PayPal dashboard
3. **Domain Verification**: Verify your domain with PayPal
4. **Testing**: Thoroughly test all payment flows

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

### Code Quality
- Use type hints throughout
- Follow PEP 8 style guidelines
- Add docstrings to all functions
- Use async/await patterns for I/O operations

### API Documentation
- Interactive API docs available at `http://localhost:8000/docs`
- OpenAPI specification at `http://localhost:8000/openapi.json`

## Troubleshooting

### Common Issues

1. **PayPal Configuration Error**:
   - Check that `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` are set
   - Verify you're using the correct mode (sandbox/live)

2. **CORS Errors**:
   - Ensure `FRONTEND_URL` is correctly set
   - Check that your frontend URL is in the CORS allow list

3. **Payment Capture Fails**:
   - Verify the PayPal order ID is correct
   - Check that the order status is "APPROVED"
   - Ensure you're not trying to capture the same payment twice

### Debug Mode
Set `DEBUG=true` in your `.env` file for detailed error messages and logging.

## Support

For issues related to:
- **PayPal Integration**: Check [PayPal Developer Documentation](https://developer.paypal.com/docs/)
- **FastAPI**: Check [FastAPI Documentation](https://fastapi.tiangolo.com/)
- **This Implementation**: Check the code comments and logs

## License

This project is licensed under the MIT License. 