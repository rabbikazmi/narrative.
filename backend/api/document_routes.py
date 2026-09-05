from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from backend.document.parser import parse_file
from backend.document.structure import structure_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    try:
        document = structure_document(file.filename or "document.txt", parse_file(file.filename or "", await file.read()))
        if not any(section.sentences for section in document.sections):
            raise ValueError("The document contains no detectable sentences")
        return (await request.app.state.reader.add_document(document)).model_dump()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{document_id}")
async def get_document(request: Request, document_id: str):
    document = request.app.state.reader.documents.get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document.model_dump()
