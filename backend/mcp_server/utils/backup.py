"""Automated Neo4j backup strategy."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Neo4jBackupManager:
    """Automated Neo4j backup management."""
    
    def __init__(
        self,
        backup_dir: str = "/backups",
        container_name: str = "ultimate_mcp_neo4j",
        retention_days: int = 7,
        max_backups: int = 10,
    ):
        self.backup_dir = Path(backup_dir)
        self.container_name = container_name
        self.retention_days = retention_days
        self.max_backups = max_backups
        
        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_backup(self) -> Optional[Path]:
        """Create a new backup of the Neo4j database."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"neo4j_backup_{timestamp}.dump"
        backup_path = self.backup_dir / backup_name
        
        try:
            # Create backup using neo4j-admin dump
            cmd = [
                "docker", "exec", self.container_name,
                "neo4j-admin", "database", "dump", "neo4j",
                "--to-path=/backups",
                f"--overwrite-destination=true"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Copy backup from container to host
                copy_cmd = [
                    "docker", "cp",
                    f"{self.container_name}:/backups/neo4j.dump",
                    str(backup_path)
                ]
                
                copy_process = await asyncio.create_subprocess_exec(
                    *copy_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                
                await copy_process.communicate()
                
                if copy_process.returncode == 0:
                    logger.info("Backup created successfully", extra={
                        "backup_path": str(backup_path),
                        "size_mb": backup_path.stat().st_size / (1024 * 1024)
                    })
                    return backup_path
                else:
                    logger.error("Failed to copy backup from container")
            else:
                logger.error("Backup creation failed", extra={
                    "stderr": stderr.decode() if stderr else "No error output"
                })
        
        except Exception as e:
            logger.error("Backup creation exception", extra={"error": str(e)})
        
        return None
    
    async def restore_backup(self, backup_path: Path) -> bool:
        """Restore database from backup."""
        if not backup_path.exists():
            logger.error("Backup file not found", extra={"path": str(backup_path)})
            return False
        
        try:
            # Stop Neo4j service
            stop_cmd = ["docker", "exec", self.container_name, "neo4j", "stop"]
            await asyncio.create_subprocess_exec(*stop_cmd)
            
            # Wait for service to stop
            await asyncio.sleep(5)
            
            # Copy backup to container
            copy_cmd = [
                "docker", "cp",
                str(backup_path),
                f"{self.container_name}:/backups/restore.dump"
            ]
            
            copy_process = await asyncio.create_subprocess_exec(
                *copy_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            await copy_process.communicate()
            
            if copy_process.returncode != 0:
                logger.error("Failed to copy backup to container")
                return False
            
            # Restore database
            restore_cmd = [
                "docker", "exec", self.container_name,
                "neo4j-admin", "database", "load", "neo4j",
                "--from-path=/backups",
                "--overwrite-destination=true"
            ]
            
            restore_process = await asyncio.create_subprocess_exec(
                *restore_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await restore_process.communicate()
            
            if restore_process.returncode == 0:
                # Start Neo4j service
                start_cmd = ["docker", "exec", self.container_name, "neo4j", "start"]
                await asyncio.create_subprocess_exec(*start_cmd)
                
                logger.info("Database restored successfully", extra={
                    "backup_path": str(backup_path)
                })
                return True
            else:
                logger.error("Database restore failed", extra={
                    "stderr": stderr.decode() if stderr else "No error output"
                })
        
        except Exception as e:
            logger.error("Restore exception", extra={"error": str(e)})
        
        return False
    
    async def cleanup_old_backups(self) -> None:
        """Remove old backups based on retention policy."""
        try:
            backups = list(self.backup_dir.glob("neo4j_backup_*.dump"))
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove backups older than retention period
            cutoff_time = datetime.now() - timedelta(days=self.retention_days)
            
            removed_count = 0
            for backup in backups:
                backup_time = datetime.fromtimestamp(backup.stat().st_mtime)
                
                # Keep max_backups most recent, regardless of age
                if len(backups) - removed_count <= self.max_backups:
                    break
                
                if backup_time < cutoff_time:
                    backup.unlink()
                    removed_count += 1
                    logger.info("Removed old backup", extra={"path": str(backup)})
            
            # Also enforce max backup count
            remaining_backups = list(self.backup_dir.glob("neo4j_backup_*.dump"))
            remaining_backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            if len(remaining_backups) > self.max_backups:
                for backup in remaining_backups[self.max_backups:]:
                    backup.unlink()
                    removed_count += 1
                    logger.info("Removed excess backup", extra={"path": str(backup)})
            
            if removed_count > 0:
                logger.info("Backup cleanup completed", extra={"removed": removed_count})
        
        except Exception as e:
            logger.error("Backup cleanup failed", extra={"error": str(e)})
    
    async def list_backups(self) -> list[dict]:
        """List available backups with metadata."""
        backups = []
        
        try:
            for backup_path in self.backup_dir.glob("neo4j_backup_*.dump"):
                stat = backup_path.stat()
                backups.append({
                    "name": backup_path.name,
                    "path": str(backup_path),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "age_days": (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days,
                })
            
            # Sort by creation time, newest first
            backups.sort(key=lambda x: x["created_at"], reverse=True)
        
        except Exception as e:
            logger.error("Failed to list backups", extra={"error": str(e)})
        
        return backups
    
    async def schedule_backups(self, interval_hours: int = 24) -> None:
        """Schedule automatic backups."""
        logger.info("Starting backup scheduler", extra={"interval_hours": interval_hours})
        
        while True:
            try:
                # Create backup
                backup_path = await self.create_backup()
                
                if backup_path:
                    # Cleanup old backups
                    await self.cleanup_old_backups()
                
                # Wait for next backup
                await asyncio.sleep(interval_hours * 3600)
            
            except Exception as e:
                logger.error("Backup scheduler error", extra={"error": str(e)})
                # Wait 1 hour before retrying on error
                await asyncio.sleep(3600)


# Global backup manager
_backup_manager: Optional[Neo4jBackupManager] = None


def get_backup_manager() -> Neo4jBackupManager:
    """Get global backup manager."""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = Neo4jBackupManager()
    return _backup_manager


def init_backup_manager(**kwargs) -> Neo4jBackupManager:
    """Initialize backup manager."""
    global _backup_manager
    _backup_manager = Neo4jBackupManager(**kwargs)
    return _backup_manager
