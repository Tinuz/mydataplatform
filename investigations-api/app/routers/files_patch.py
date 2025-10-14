# Read the entire file
with open("/app/app/routers/files.py", "r") as f:
    lines = f.readlines()

# Find the list_files function and modify it
output_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Disable response_model for list_files
    if "response_model=List[DataSourceResponse]," in line and i > 0 and "list_files" in "".join(lines[max(0,i-10):i]):
        output_lines.append("    # response_model=List[DataSourceResponse],  # Disabled to avoid metadata issues\n")
        i += 1
        continue
    
    # Replace "return files" with manual dict conversion
    if line.strip() == "return files" and "list_files" in "".join(lines[max(0,i-50):i]):
        output_lines.append("        # Manual conversion to handle datetime serialization\n")
        output_lines.append("        return [{")
        output_lines.append("""
            "source_id": f.source_id,
            "investigation_id": f.investigation_id,
            "source_type": f.source_type,
            "provider": f.provider,
            "file_name": f.file_name,
            "file_path": f.file_path,
            "file_size_bytes": f.file_size_bytes,
            "file_hash": f.file_hash,
            "received_date": f.received_date.isoformat() if hasattr(f.received_date, "isoformat") else str(f.received_date),
            "uploaded_by": f.uploaded_by,
            "processing_status": f.processing_status,
            "processing_started_at": f.processing_started_at.isoformat() if f.processing_started_at and hasattr(f.processing_started_at, "isoformat") else None,
            "processing_completed_at": f.processing_completed_at.isoformat() if f.processing_completed_at and hasattr(f.processing_completed_at, "isoformat") else None,
            "processor_pipeline": f.processor_pipeline,
            "error_message": f.error_message,
            "metadata": f.metadata or {},
            "created_at": f.created_at.isoformat() if f.created_at and hasattr(f.created_at, "isoformat") else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at and hasattr(f.updated_at, "isoformat") else None
        } for f in files]
""")
        i += 1
        continue
    
    output_lines.append(line)
    i += 1

# Write back
with open("/app/app/routers/files.py", "w") as f:
    f.writelines(output_lines)

print("Patched files.py successfully!")
