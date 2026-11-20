// ============================================================================
// Tap hop script JS/TBEL cho tung Node trong RuleChain Smart Room (T12)
// Dung de copy-paste nhanh khi tao hoac chinh sua truc tiep tren giao dien CoreIOT.
// ============================================================================

// --- 1. Node "Phan loai nguong nhiet do" (Switch Node) ---
// Lua chon scriptLang: JS (hoac TBEL neu CoreIOT bat mac dinh TBEL)
function switchTemperatureThreshold(msg, metadata, msgType) {
  if (msg.temperature == null) {
    return ['Ignore'];
  }
  var temp = Number(msg.temperature);
  if (temp > 32) {
    return ['HighTemp'];
  }
  if (temp <= 30) {
    return ['NormalTemp'];
  }
  // Vung tre (Hysteresis: 30 < T <= 32): giu nguyen trang thai hien tai
  return ['Hysteresis'];
}

// --- 2. Node "Create Alarm: High Temperature" (Details Builder) ---
// LUU Y QUAN TRONG: Chi noi nhanh "Created" sang node RPC ON; KHONG noi nhanh "Updated".
function buildCreateAlarmDetails(msg, metadata, msgType) {
  var details = {};
  if (metadata.prevAlarmDetails) {
    details = JSON.parse(metadata.prevAlarmDetails);
  }
  details.temperature = msg.temperature;
  details.humidity = msg.humidity;
  details.threshold = 32;
  return details;
}

// --- 3. Node "Clear Alarm: High Temperature" (Details Builder) ---
// LUU Y QUAN TRONG: Chi noi nhanh "Cleared" sang node RPC OFF; KHONG noi nhanh "False".
function buildClearAlarmDetails(msg, metadata, msgType) {
  var details = {};
  if (metadata.prevAlarmDetails) {
    details = JSON.parse(metadata.prevAlarmDetails);
  }
  details.clearedTemperature = msg.temperature;
  details.clearedThreshold = 30;
  return details;
}

// --- 4. Node "Tao lenh RPC setCooling(true)" (Transform Script Node) ---
function transformRpcCoolingOn(msg, metadata, msgType) {
  return {
    msg: {
      method: 'setCooling',
      params: { state: true }
    },
    metadata: metadata,
    msgType: 'RPC_CALL_FROM_SERVER_TO_DEVICE'
  };
}

// --- 5. Node "Tao lenh RPC setCooling(false)" (Transform Script Node) ---
function transformRpcCoolingOff(msg, metadata, msgType) {
  return {
    msg: {
      method: 'setCooling',
      params: { state: false }
    },
    metadata: metadata,
    msgType: 'RPC_CALL_FROM_SERVER_TO_DEVICE'
  };
}

// --- 6. Node "Log ket qua RPC" (Log Node) ---
function logRpcOutcome(msg, metadata, msgType) {
  return (
    'SmartRoom Auto RPC -> msg=' +
    JSON.stringify(msg) +
    ', metadata=' +
    JSON.stringify(metadata)
  );
}
