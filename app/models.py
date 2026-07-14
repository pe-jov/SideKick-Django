"""Modeli baze podataka za aplikaciju SideKick."""

# Author Petar Jovanovic
from urllib.parse import urlparse

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


DEFAULT_AVATAR_URL = "/static/app/img/avatar-placeholder.svg"

SPACE_COVERS = {
    "product-narrative-lab": "https://images.unsplash.com/photo-1516321165247-4aa89a48be28?auto=format&fit=crop&w=900&q=80",
    "material-futures": "https://images.unsplash.com/photo-1517705008128-361805f42e86?auto=format&fit=crop&w=900&q=80",
    "urban-cabin-study": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=80",
    "balkan-food-atlas": "https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=900&q=80",
}


class TimestampedModel(models.Model):
    """Apstraktni bazni model koji čuva vreme kreiranja i poslednje izmene."""

    created_at = models.DateTimeField(db_column="createdAt")
    updated_at = models.DateTimeField(db_column="updatedAt")

    class Meta:
        abstract = True


class User(TimestampedModel):
    """Model korisnika koji čuva osnovne podatke naloga i putanju do avatara."""

    user_id = models.AutoField(primary_key=True, db_column="userId")
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255, db_column="passwordHash")
    full_name = models.CharField(max_length=255, db_column="fullName")
    avatar_path = models.CharField(max_length=500, blank=True, db_column="avatarPath")

    class Meta:
        db_table = "USER"
        ordering = ["user_id"]

    def __str__(self):
        """Vraća puno ime korisnika za tekstualni prikaz modela."""
        return self.full_name

    @property
    def avatar_url(self):
        """Vraća URL avatara korisnika ili podrazumevanu siluetu ako avatar ne postoji."""
        return self.avatar_path or DEFAULT_AVATAR_URL


class AuthToken(models.Model):
    """Model tokena koji služi za autentifikaciju web i ekstenzionih klijenata."""

    class ClientType(models.TextChoices):
        """Definiše tip klijenta kojem je token izdat."""

        WEB = "web", "Web"
        EXTENSION = "extension", "Extension"

    token_id = models.AutoField(primary_key=True, db_column="tokenId")
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="auth_tokens", db_column="userId"
    )
    token_value = models.CharField(max_length=255, unique=True, db_column="tokenValue")
    client_type = models.CharField(
        max_length=20, choices=ClientType.choices, db_column="clientType"
    )
    issued_at = models.DateTimeField(db_column="issuedAt")
    expires_at = models.DateTimeField(db_column="expiresAt", blank=True, null=True)
    is_revoked = models.BooleanField(default=False, db_column="isRevoked")

    class Meta:
        db_table = "AUTH_TOKEN"
        ordering = ["token_id"]

    def __str__(self):
        """Vraća tekstualni opis tokena sa korisnikom i tipom klijenta."""
        return f"{self.user.full_name} ({self.client_type})"


class ResearchSpace(TimestampedModel):
    """Model istraživačkog prostora u kome korisnici organizuju sačuvane stavke."""

    space_id = models.AutoField(primary_key=True, db_column="spaceId")
    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="owned_spaces", db_column="ownerId"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False, db_column="isArchived")

    class Meta:
        db_table = "RESEARCH_SPACE"
        ordering = ["space_id"]

    def __str__(self):
        """Vraća naziv prostora za tekstualni prikaz modela."""
        return self.name

    @property
    def image_url(self):
        """Vraća URL naslovne slike prostora na osnovu njegovog naziva."""
        return SPACE_COVERS.get(
            slugify(self.name),
            "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=900&q=80",
        )


class Membership(TimestampedModel):
    """Model članstva koji povezuje korisnika sa prostorom i njegovom ulogom."""

    class Role(models.TextChoices):
        """Definiše ulogu korisnika unutar prostora."""

        COLLABORATOR = "collaborator", "Collaborator"
        VIEWER = "viewer", "Viewer"

    class Status(models.TextChoices):
        """Definiše status članstva korisnika u prostoru."""

        ACTIVE = "active", "Active"
        REMOVED = "removed", "Removed"

    membership_id = models.AutoField(primary_key=True, db_column="membershipId")
    space = models.ForeignKey(
        ResearchSpace, on_delete=models.CASCADE, related_name="memberships", db_column="spaceId"
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="memberships", db_column="userId"
    )
    joined_via = models.ForeignKey(
        "ShareLink",
        on_delete=models.SET_NULL,
        related_name="granted_memberships",
        db_column="joinedVia",
        blank=True,
        null=True,
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(max_length=20, choices=Status.choices)

    class Meta:
        db_table = "MEMBERSHIP"
        ordering = ["membership_id"]
        constraints = [
            models.UniqueConstraint(fields=["space", "user"], name="uq_membership_space_user")
        ]

    def __str__(self):
        """Vraća tekstualni opis članstva korisnika u prostoru."""
        return f"{self.user.full_name} in {self.space.name}"


class CollaborationRequest(models.Model):
    """Model zahteva za dobijanje saradničkog pristupa prostoru."""

    class Status(models.TextChoices):
        """Definiše status zahteva za saradnju."""

        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    request_id = models.AutoField(primary_key=True, db_column="requestId")
    space = models.ForeignKey(
        ResearchSpace,
        on_delete=models.CASCADE,
        related_name="collaboration_requests",
        db_column="spaceId",
    )
    requester = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="requested_collaborations",
        db_column="requesterId",
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="resolved_collaborations",
        db_column="resolvedBy",
        blank=True,
        null=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    message = models.TextField(blank=True)
    requested_at = models.DateTimeField(db_column="requestedAt")
    resolved_at = models.DateTimeField(db_column="resolvedAt", blank=True, null=True)

    class Meta:
        db_table = "COLLABORATION_REQUEST"
        ordering = ["request_id"]

    def __str__(self):
        """Vraća tekstualni opis zahteva za saradnju."""
        return f"{self.requester.full_name} -> {self.space.name}"


class Item(TimestampedModel):
    """Model stavke koja predstavlja tekst, link ili sliku sačuvanu u prostoru."""

    class ItemType(models.TextChoices):
        """Definiše tip sadržaja koji stavka čuva."""

        TEXT = "text", "Text"
        LINK = "link", "Link"
        IMAGE = "image", "Image"

    class SourcePlatform(models.TextChoices):
        """Definiše sa koje platforme je stavka sačuvana."""

        WEB = "web", "Web"
        EXTENSION = "extension", "Extension"

    item_id = models.AutoField(primary_key=True, db_column="itemId")
    space = models.ForeignKey(
        ResearchSpace, on_delete=models.CASCADE, related_name="items", db_column="spaceId"
    )
    added_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="items", db_column="addedBy"
    )
    item_type = models.CharField(max_length=20, choices=ItemType.choices, db_column="itemType")
    content_text = models.TextField(blank=True, db_column="contentText")
    source_url = models.CharField(max_length=500, blank=True, db_column="sourceUrl")
    image_path = models.CharField(max_length=500, blank=True, db_column="imagePath")
    title = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    source_platform = models.CharField(
        max_length=20, choices=SourcePlatform.choices, db_column="sourcePlatform"
    )
    captured_url = models.CharField(max_length=500, blank=True, db_column="capturedUrl")
    page_title = models.CharField(max_length=255, blank=True, db_column="pageTitle")

    class Meta:
        db_table = "ITEM"
        ordering = ["item_id"]

    def __str__(self):
        """Vraća tekstualni opis stavke i prostora kome pripada."""
        return f"{self.item_type} in {self.space.name}"

    @property
    def domain(self):
        """Vraća domen izvornog ili zabeleženog URL-a stavke."""
        url = self.source_url or self.captured_url
        if not url:
            return ""
        return urlparse(url).netloc

    @property
    def image_url(self):
        """Vraća URL slike stavke iz lokalne putanje ili izvornog linka."""
        if self.image_path:
            return self.image_path
        if self.source_url:
            return self.source_url
        return ""


class ShareLink(models.Model):
    """Model linka za deljenje prostora sa drugim korisnicima."""

    share_link_id = models.AutoField(primary_key=True, db_column="shareLinkId")
    space = models.ForeignKey(
        ResearchSpace, on_delete=models.CASCADE, related_name="share_links", db_column="spaceId"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="share_links", db_column="createdBy"
    )
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(db_column="createdAt")
    expires_at = models.DateTimeField(db_column="expiresAt", blank=True, null=True)
    is_active = models.BooleanField(default=True, db_column="isActive")

    class Meta:
        db_table = "SHARE_LINK"
        ordering = ["share_link_id"]

    def __str__(self):
        """Vraća tekstualni opis deljenog linka."""
        return f"{self.space.name} share link"

    @property
    def is_available(self):
        """Vraća informaciju da li je deljeni link trenutno aktivan i neistekao."""
        return self.is_active and (self.expires_at is None or self.expires_at > timezone.now())
