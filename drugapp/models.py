from django.db import models

class Drug(models.Model):
    itemName = models.CharField("제품명", max_length=255)
    efcyQesitm = models.TextField("약의 효능", blank=True, null=True)
    atpnQesitm = models.TextField("주의사항", blank=True, null=True)
    depositMethodQesitm = models.TextField("보관 방법", blank=True, null=True)

    def __str__(self):
        return self.itemName
