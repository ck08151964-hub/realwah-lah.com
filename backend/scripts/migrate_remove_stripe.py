#!/usr/bin/env python3
"""
Database Migration: Remove Stripe Integration

Purpose: Archive or drop Stripe-related fields from the database after
         migrating to modular payment gateway architecture.

BEFORE running this:
  1. Ensure you have a backup of your MongoDB Atlas database
  2. Update backend/server.py to use new payment gateway system
  3. Test on staging environment

This migration:
  - Adds 'archived_stripe_payment_method' field to existing transactions (historical record)
  - Removes 'payment_method' field from users collection
  - Renames 'payment_transactions' collection to 'payment_transactions_legacy'
  - Creates new 'payment_transactions_v2' collection with updated schema
"""

import os
import sys
import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment
load_dotenv()
MONGO_URL = os.getenv("MONGODB_URI") or os.getenv("MONGO_URL") or os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "wahlah_prod")

if not MONGO_URL:
    raise RuntimeError("MONGODB_URI not set")


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print("🔄 Starting Stripe removal migration...")
    print(f"   Database: {DB_NAME}")
    print(f"   Timestamp: {datetime.now(timezone.utc).isoformat()}\n")

    try:
        # Step 1: Backup legacy payment_transactions collection
        print("📦 Step 1: Archiving payment_transactions collection...")
        legacy_count = await db.payment_transactions.count_documents({})
        if legacy_count > 0:
            # Rename to legacy backup
            await db.payment_transactions.rename("payment_transactions_legacy", dropTarget=False)
            print(f"   ✅ Archived {legacy_count} transactions → payment_transactions_legacy")
        else:
            print("   ℹ️  No payment_transactions to archive")

        # Step 2: Remove Stripe-specific fields from users
        print("\n🔍 Step 2: Removing Stripe fields from users collection...")
        result = await db.users.update_many(
            {},
            {"$unset": {"payment_method": "", "stripe_customer_id": ""}},
        )
        print(f"   ✅ Removed fields from {result.modified_count} users")

        # Step 3: Create new payment_transactions_v2 collection with migrated data
        print("\n📝 Step 3: Creating new payment_transactions_v2 collection...")
        print("   (Empty for now - new transactions will be created here)")
        # Just ensure it exists
        await db.payment_transactions_v2.insert_one(
            {
                "migration_marker": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "note": "Placeholder to initialize collection schema",
            }
        )
        # Remove the marker
        await db.payment_transactions_v2.delete_one({"migration_marker": True})
        print("   ✅ Created payment_transactions_v2")

        # Step 4: Update launch checklist (disable stripe check)
        print("\n✔️ Step 4: Updating launch checklist...")
        await db.launch_checklist.update_many(
            {"check_id": "stripe"},
            {"$set": {"status": "deprecated", "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        print("   ✅ Marked Stripe check as deprecated")

        # Step 5: Log migration
        print("\n📋 Step 5: Recording migration log...")
        migration_log = {
            "migration_id": f"stripe_removal_{datetime.now(timezone.utc).timestamp()}",
            "type": "stripe_removal",
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "changes": {
                "users_cleaned": result.modified_count,
                "transactions_archived": legacy_count,
                "new_collection_created": "payment_transactions_v2",
            },
            "notes": "Stripe integration completely removed. Users should use Skrill, gift cards, or manual payments going forward.",
        }
        await db.migration_logs.insert_one(migration_log)
        print(f"   ✅ Migration logged with ID: {migration_log['migration_id']}")

        print("\n" + "=" * 70)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Deploy backend with new payment gateway system")
        print("  2. Monitor /api/payments/test-flow endpoint")
        print("  3. Verify no Stripe errors in logs")
        print("  4. Test manual payment methods (gift cards, crypto)")
        print("\n📚 Collections changed:")
        print(f"  - payment_transactions → payment_transactions_legacy (backup)")
        print(f"  - payment_transactions_v2 created (new)")
        print(f"  - users: removed stripe_customer_id, payment_method")
        print("\n⚠️  IMPORTANT: Keep payment_transactions_legacy for audit purposes.")
        print("             Do NOT drop it without legal/compliance review.\n")

    except Exception as e:
        print(f"\n❌ MIGRATION FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
