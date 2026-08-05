const baseline = "2026-05";
const cloud = "Cloud Computing & Storage";
const floor = 1000;
let finFixed = 0;
db.financial_entries.find({component: cloud}).forEach(row => {
  const updates = {};
  ["fund_released","fund_utilized","fund_target","fund_allocated"].forEach(f => {
    const v = row[f];
    if (typeof v === "number" && Math.abs(v) >= floor) updates[f] = Math.round((v/1e7)*10000)/10000;
  });
  if (Object.keys(updates).length) {
    const released = updates.fund_released ?? row.fund_released;
    const utilized = updates.fund_utilized ?? row.fund_utilized;
    if (released && utilized != null) {
      updates.utilisation_percent = Math.round((100*utilized/released)*100)/100;
      updates.variance = Math.round((released-utilized)*10000)/10000;
    }
    db.financial_entries.updateOne({_id: row._id}, {$set: updates});
    finFixed++;
  }
});
let physMirrored = 0;
db.physical_entries.find({component: cloud, reporting_period: "2026-07"}).forEach(row => {
  const q = {
    high_court: row.high_court, component: cloud, indicator: row.indicator,
    reporting_period: baseline, district: row.district ?? null,
    storage_type: row.storage_type || "Block Storage",
  };
  const payload = Object.assign({}, row); delete payload._id; Object.assign(payload, q);
  const existing = db.physical_entries.findOne(q);
  if (existing) {
    db.physical_entries.updateOne({_id: existing._id}, {$set: {
      target: payload.target, achieved: payload.achieved, percent: payload.percent,
      rag: payload.rag, remarks: payload.remarks, uom: payload.uom
    }});
  } else { db.physical_entries.insertOne(payload); }
  physMirrored++;
});
let finMirrored = 0;
db.financial_entries.find({component: cloud, reporting_period: "2026-07"}).forEach(row => {
  const q = {
    high_court: row.high_court, component: cloud,
    reporting_period: baseline, district: row.district ?? null,
  };
  const payload = Object.assign({}, row); delete payload._id; Object.assign(payload, q);
  const existing = db.financial_entries.findOne(q);
  if (existing) {
    db.financial_entries.updateOne({_id: existing._id}, {$set: {
      fund_target: payload.fund_target, fund_allocated: payload.fund_allocated,
      fund_released: payload.fund_released, fund_utilized: payload.fund_utilized,
      utilisation_percent: payload.utilisation_percent, variance: payload.variance,
      rag: payload.rag, remarks: payload.remarks, description: payload.description
    }});
  } else { db.financial_entries.insertOne(payload); }
  finMirrored++;
});
print("finFixed="+finFixed+" physMirrored="+physMirrored+" finMirrored="+finMirrored);
printjson(db.physical_entries.aggregate([
  {$match:{component:cloud, reporting_period:baseline}},
  {$group:{_id:null,n:{$sum:1},a:{$sum:{$ifNull:["$achieved",0]}}}}
]).toArray());
printjson(db.financial_entries.aggregate([
  {$match:{component:cloud, reporting_period:baseline}},
  {$group:{_id:null,n:{$sum:1},r:{$sum:{$ifNull:["$fund_released",0]}},u:{$sum:{$ifNull:["$fund_utilized",0]}}}}
]).toArray());
