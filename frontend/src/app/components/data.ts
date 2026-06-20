import type { Member, MemberDetail, SuggestedQuestion } from './types';

export const MEMBERS: Member[] = [
  {
    id: 'member_001',
    name: 'Maria S.',
    age: 54,
    plan: 'Silver PPO',
    summary: 'Diabetes care, metformin, recent lab claim',
    member_ref: 'member_001',
  },
  {
    id: 'member_002',
    name: 'James R.',
    age: 42,
    plan: 'Bronze HMO',
    summary: 'Recent MRI claim, orthopedic visit',
    member_ref: 'member_002',
  },
  {
    id: 'member_003',
    name: 'Asha P.',
    age: 31,
    plan: 'Gold EPO',
    summary: 'Pregnancy care, upcoming specialist visit',
    member_ref: 'member_003',
  },
];

export const MEMBER_DETAILS: Record<string, MemberDetail> = {
  member_001: {
    planType: 'Silver PPO — Individual',
    deductible: { used: 2500, total: 2500 },
    oop: { used: 1230, total: 7000 },
    medications: ['Metformin 1000mg (twice daily)', 'Lisinopril 10mg (once daily)', 'Atorvastatin 20mg (once daily)'],
    conditions: ['Type 2 diabetes', 'High blood pressure', 'High cholesterol'],
    kbTopics: ['Type 2 Diabetes', 'High Blood Pressure', 'High Cholesterol'],
    recentClaims: [
      { description: 'Comprehensive Metabolic Panel', date: '2026-05-28', amount: 245, status: 'Processing' },
      { description: 'PCP Office Visit', date: '2026-04-10', amount: 180, status: 'Paid' },
      { description: 'HbA1c Test', date: '2026-03-15', amount: 62, status: 'Paid' },
    ],
    recentProviders: [
      { name: 'Dr. Linda Chen', specialty: 'Endocrinology' },
      { name: 'Dr. James Park', specialty: 'Primary Care' },
    ],
    note: 'Member has managed type 2 diabetes for 8 years. Deductible met. Good medication adherence on record.',
  },
  member_002: {
    planType: 'Bronze HMO — Individual',
    deductible: { used: 4200, total: 6500 },
    oop: { used: 3420, total: 8000 },
    medications: ['Ibuprofen 600mg (as needed)', 'Cyclobenzaprine 5mg (as needed)', 'Omeprazole 20mg (daily)'],
    conditions: ['Low back pain', 'Orthopedic injury'],
    kbTopics: ['Low Back Pain', 'Injuries Fractures'],
    recentClaims: [
      { description: 'MRI Lumbar Spine', date: '2026-06-01', amount: 1800, status: 'Denied' },
      { description: 'Orthopedic Office Visit', date: '2026-05-15', amount: 320, status: 'Paid' },
      { description: 'X-Ray Lumbar', date: '2026-04-22', amount: 180, status: 'Paid' },
    ],
    recentProviders: [
      { name: 'Dr. Kevin Williams', specialty: 'Orthopedics' },
      { name: 'Dr. Rosa Martinez', specialty: 'Primary Care' },
    ],
    note: 'Active claim dispute for MRI denial. Member seeking appeal guidance. Deductible partially met.',
  },
  member_003: {
    planType: 'Gold EPO — Individual + Maternity',
    deductible: { used: 500, total: 1500 },
    oop: { used: 200, total: 4000 },
    medications: ['Prescription Prenatal Vitamins (daily)', 'Folic Acid 400mcg (daily)', 'Iron 27mg (daily)'],
    conditions: ['Pregnancy', 'Anemia'],
    kbTopics: ['Pregnancy', 'Anemia'],
    recentClaims: [
      { description: 'OB Prenatal Visit', date: '2026-06-10', amount: 290, status: 'Paid' },
      { description: 'Prenatal Lab Panel', date: '2026-05-22', amount: 180, status: 'Paid' },
      { description: 'First Trimester Ultrasound', date: '2026-05-08', amount: 420, status: 'Paid' },
    ],
    recentProviders: [
      { name: 'Dr. Sarah Thompson', specialty: 'OB/GYN' },
      { name: 'Dr. Anil Patel', specialty: 'Maternal-Fetal Medicine' },
    ],
    note: 'Currently 18 weeks pregnant. Upcoming MFM specialist visit on 2026-06-24. Gold plan with strong maternity coverage.',
  },
};

export const SUGGESTED_QUESTIONS: Record<string, SuggestedQuestion[]> = {
  member_001: [
    { label: 'Medication side effects', question: 'What are the common side effects of metformin?', intent: 'medication' },
    { label: 'CGM coverage', question: 'Is continuous glucose monitoring covered under my Silver PPO plan?', intent: 'benefits' },
    { label: 'Lab claim status', question: 'What is the status of my recent lab work claim?', intent: 'claims' },
    { label: 'Endocrinologist network', question: 'Which endocrinologists are in-network for my Silver PPO?', intent: 'providers' },
    { label: 'Emergency test', question: 'I have chest pain right now, what should I do?', intent: 'safety' },
  ],
  member_002: [
    { label: 'MRI claim appeal', question: 'How do I appeal my recent MRI claim denial?', intent: 'claims' },
    { label: 'Orthopedic coverage', question: 'What is my coverage for orthopedic surgery under my Bronze HMO?', intent: 'benefits' },
    { label: 'Specialist referral', question: 'How do I get a referral to an orthopedic specialist?', intent: 'providers' },
    { label: 'Physical therapy', question: 'Is physical therapy covered after orthopedic surgery under my plan?', intent: 'benefits' },
    { label: 'Emergency test', question: 'I have chest pain right now, what should I do?', intent: 'safety' },
  ],
  member_003: [
    { label: 'Prenatal coverage', question: 'What prenatal services are covered under my Gold EPO plan?', intent: 'benefits' },
    { label: 'Specialist visit', question: 'Do I need a referral for my upcoming specialist visit with Dr. Patel?', intent: 'providers' },
    { label: 'Prenatal vitamins', question: 'Are prescription prenatal vitamins covered by my Gold EPO plan?', intent: 'medication' },
    { label: 'Labor & delivery cost', question: 'What is my estimated out-of-pocket cost for labor and delivery?', intent: 'claims' },
    { label: 'Emergency test', question: 'I have chest pain right now, what should I do?', intent: 'safety' },
  ],
};
