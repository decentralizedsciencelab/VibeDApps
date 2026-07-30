from django.db import models

# Create your models here.
class Transaction(models.Model):
    """Model to store transaction data"""
    tx_hash = models.CharField(max_length=66, unique=True)
    block_number = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=100)
    status = models.BooleanField(default=True)
    from_address = models.CharField(max_length=42)
    to_address = models.CharField(max_length=42)
    value = models.CharField(max_length=100, default='0')
    gas_used = models.PositiveIntegerField()
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return self.tx_hash
