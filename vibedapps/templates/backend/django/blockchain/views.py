from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.conf import settings
import json

from .web3_client import Web3Client
from .serializers import TransactionSerializer
from .models import Transaction

# Initialize Web3 client
w3_client = Web3Client(
    rpc_url=settings.RPC_URL,
    contract_address=settings.CONTRACT_ADDRESS,
    private_key=settings.PRIVATE_KEY
)

@api_view(['GET'])
def health_check(request):
    """Health check endpoint"""
    is_connected = w3_client.is_connected()
    return Response({
        'status': 'healthy' if is_connected else 'unhealthy',
        'blockchain_connected': is_connected,
        'contract_address': settings.CONTRACT_ADDRESS
    })

@api_view(['GET'])
def get_contract_info(request):
    """Get contract information"""
    try:
        info = w3_client.get_contract_info()
        return Response(info)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def read_contract(request, method):
    """Read data from contract"""
    try:
        # Get arguments from query params
        args = []
        if 'args' in request.query_params:
            args = json.loads(request.query_params.get('args'))
        
        # Call contract method
        result = w3_client.read_contract(method, args)
        return Response({'result': result})
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def write_contract(request, method):
    """Write data to contract"""
    try:
        # Get arguments from request data
        args = request.data.get('args', [])
        
        # Call contract method
        tx_receipt = w3_client.write_contract(method, args)
        
        # Save transaction to database
        tx_hash = tx_receipt['transactionHash'].hex()
        tx = Transaction(
            tx_hash=tx_hash,
            block_number=tx_receipt['blockNumber'],
            method=method,
            status=tx_receipt['status'] == 1,
            from_address=w3_client.get_address(),
            to_address=settings.CONTRACT_ADDRESS,
            gas_used=tx_receipt['gasUsed']
        )
        tx.save()
        
        serializer = TransactionSerializer(tx)
        return Response(serializer.data)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_events(request, event_name):
    """Get contract events"""
    try:
        # Get filter parameters
        from_block = int(request.query_params.get('from_block', 0))
        to_block = request.query_params.get('to_block', 'latest')
        filters = {}
        if 'filters' in request.query_params:
            filters = json.loads(request.query_params.get('filters'))
        
        # Get events
        events = w3_client.get_events(event_name, from_block, to_block, filters)
        return Response({'events': events})
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_network_status(request):
    """Get network status"""
    try:
        status_info = w3_client.get_network_status()
        return Response(status_info)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_gas_price(request):
    """Get current gas price"""
    try:
        gas_info = w3_client.get_gas_price()
        return Response(gas_info)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_block_info(request, block_number):
    """Get block information"""
    try:
        # Convert to int if not 'latest'
        if block_number != 'latest':
            block_number = int(block_number)
        
        block_info = w3_client.get_block_info(block_number)
        return Response(block_info)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Transaction model"""
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
