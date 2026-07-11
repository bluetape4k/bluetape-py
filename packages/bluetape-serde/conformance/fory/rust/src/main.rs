use fory::{Fory, ForyStruct, Reader};
use std::env;
use std::error::Error;
use std::fs;
use std::io::{Error as IoError, ErrorKind};
use std::path::Path;

const HEADER_SIZE: usize = 20;
const SCHEMA_ID: u32 = 1_112_819_289;
const SCHEMA_VERSION: u16 = 1;
const TYPE_ID: u32 = 1001;

#[derive(ForyStruct, Debug, PartialEq)]
#[fory(evolving = false)]
struct ConformanceRecord {
    #[fory(id = 1)]
    record_id: i64,
    #[fory(id = 2)]
    name: String,
    #[fory(id = 3)]
    active: bool,
    #[fory(id = 4)]
    scores: Vec<i32>,
}

fn expected() -> ConformanceRecord {
    ConformanceRecord {
        record_id: 7,
        name: "blue".to_string(),
        active: true,
        scores: vec![1, 2, 3],
    }
}

fn new_fory() -> Result<Fory, Box<dyn Error>> {
    let mut fory = Fory::builder()
        .xlang(true)
        .compatible(false)
        .track_ref(false)
        .max_dyn_depth(64)
        .max_type_fields(256)
        .max_type_meta_bytes(4096)
        .max_schema_versions_per_type(8)
        .max_average_schema_versions_per_type(2)
        .build();
    fory.register::<ConformanceRecord>(TYPE_ID)?;
    Ok(fory)
}

fn wrap(body: &[u8]) -> Result<Vec<u8>, Box<dyn Error>> {
    let body_length = u32::try_from(body.len())?;
    let mut result = Vec::with_capacity(HEADER_SIZE + body.len());
    result.extend_from_slice(b"BTFY");
    result.push(1);
    result.push(0);
    result.extend_from_slice(&SCHEMA_ID.to_be_bytes());
    result.extend_from_slice(&SCHEMA_VERSION.to_be_bytes());
    result.extend_from_slice(&TYPE_ID.to_be_bytes());
    result.extend_from_slice(&body_length.to_be_bytes());
    result.extend_from_slice(body);
    Ok(result)
}

fn invalid(message: &'static str) -> Box<dyn Error> {
    Box::new(IoError::new(ErrorKind::InvalidData, message))
}

fn unwrap(data: &[u8]) -> Result<&[u8], Box<dyn Error>> {
    if data.len() < HEADER_SIZE || &data[..4] != b"BTFY" {
        return Err(invalid("invalid bluetape Fory envelope"));
    }
    if data[4] != 1 || data[5] != 0 {
        return Err(invalid("unsupported bluetape Fory envelope"));
    }
    if u32::from_be_bytes(data[6..10].try_into()?) != SCHEMA_ID
        || u16::from_be_bytes(data[10..12].try_into()?) != SCHEMA_VERSION
        || u32::from_be_bytes(data[12..16].try_into()?) != TYPE_ID
    {
        return Err(invalid("bluetape Fory registration mismatch"));
    }
    let body_length = u32::from_be_bytes(data[16..20].try_into()?) as usize;
    if body_length == 0 || body_length != data.len() - HEADER_SIZE {
        return Err(invalid("invalid bluetape Fory body length"));
    }
    Ok(&data[HEADER_SIZE..])
}

fn generate(path: &Path) -> Result<(), Box<dyn Error>> {
    let fory = new_fory()?;
    let mut body = Vec::new();
    fory.serialize_to(&mut body, &expected())?;
    fs::write(path, wrap(&body)?)?;
    Ok(())
}

fn verify(path: &Path) -> Result<(), Box<dyn Error>> {
    let data = fs::read(path)?;
    let body = unwrap(&data)?;
    let fory = new_fory()?;
    let mut reader = Reader::new(body);
    let result: ConformanceRecord = fory.deserialize_from(&mut reader)?;
    if reader.get_cursor() != body.len() {
        return Err(invalid("Fory body contains trailing bytes"));
    }
    if result != expected() {
        return Err(invalid(
            "Fory conformance value does not match the canonical record",
        ));
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    let arguments: Vec<String> = env::args().collect();
    if arguments.len() != 3 || !matches!(arguments[1].as_str(), "generate" | "verify") {
        return Err(invalid("usage: fory-conformance generate|verify PATH"));
    }
    let path = Path::new(&arguments[2]);
    if arguments[1] == "generate" {
        generate(path)
    } else {
        verify(path)
    }
}
