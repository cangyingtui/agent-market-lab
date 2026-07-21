import { type ReactNode, useEffect, useMemo, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams
} from "react-router-dom";
import ReactECharts from "echarts-for-react";
import zhCN from "antd/locale/zh_CN";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  Checkbox,
  Col,
  ConfigProvider,
  Descriptions,
  Divider,
  Empty,
  Form,
  Input,
  InputNumber,
  Layout,
  List,
  message,
  Modal,
  Progress,
  Radio,
  Row,
  Segmented,
  Select,
  Slider,
  Space,
  Statistic,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Timeline,
  Typography,
  theme
} from "antd";
import {
  BarChartOutlined,
  CheckCircleOutlined,
  CloudDownloadOutlined,
  CopyOutlined,
  CrownOutlined,
  DeleteOutlined,
  FileTextOutlined,
  LockOutlined,
  LoginOutlined,
  LogoutOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  SendOutlined,
  ShareAltOutlined,
  SettingOutlined,
  StopOutlined,
  UserOutlined
} from "@ant-design/icons";
import { api, clearToken, downloadWithAuth, getToken, JsonObject, setToken } from "./api";
import {
  findProductParamTemplate,
  normalizeProductSubcategory,
  PRODUCT_MAJOR_CATEGORIES,
  productSubcategoriesForMajor,
  type ProductParamTemplate,
  type ProductSubcategoryTemplate
} from "./productParamTemplates";
import "./styles.css";

const { Header, Content } = Layout;
const { Title, Text, Paragraph } = Typography;
const DEMO_ACCOUNT_USERNAMES = new Set(["normal@example", "pro@example"]);
const CONTACT_UPGRADE_MESSAGE = "如需升级专业版，请联系客服 18960333566。";
const CUSTOM_SUBCATEGORY_VALUE = "__custom_subcategory__";

function isDemoAccount(user?: User | null): boolean {
  return user?.is_demo_account === true || Boolean(user?.username && DEMO_ACCOUNT_USERNAMES.has(user.username));
}

function clearActiveProjectCache(): void {
  localStorage.removeItem("agentsim_active_project_id");
}

type User = JsonObject & {
  id: number;
  username: string;
  nickname?: string;
  email?: string;
  full_name?: string;
  avatar_url?: string;
  plan_type?: string;
  is_demo_account?: boolean;
  basic_quota_remaining?: number;
  remaining_simulations?: number | null;
};

type Project = JsonObject & {
  id: number;
  project_name: string;
  status: string;
  product_definition?: JsonObject;
  market_config?: JsonObject;
  result_data?: JsonObject;
  task_id?: string;
  draft_version?: number;
  updated_at?: string;
  created_at?: string;
};

type Category = {
  id: number;
  category: string;
  subcategory: string;
  display_name: string;
};

type FieldTemplate = {
  id: number;
  field_name: string;
  field_type?: string;
  field_desc?: string;
  unit?: string;
  ui_control?: string;
  ui_schema?: FieldUiSchema | JsonObject | null;
  default_weight?: number;
  is_required?: boolean;
};

type FieldUiSchema = JsonObject & {
  label?: string;
  controlType?: string;
  min?: number;
  max?: number;
  step?: number;
  defaultValue?: unknown;
  unit?: string;
  options?: Array<string | number>;
  hint?: string;
  defaultWeight?: number;
};

type TemplateItem = {
  id: number;
  name: string;
  description?: string;
  default_ratio?: number;
  tags?: JsonObject;
};

type ProductItem = JsonObject & {
  id: number;
  product_name?: string;
  brand?: string;
  price_cny?: number;
  specifications?: JsonObject;
};

type AssistantPage = "step1" | "step2" | "step3" | "step4";

type AssistantMessage = {
  role: "user" | "assistant";
  content: string;
};

type AssistantFieldCard = {
  key?: string;
  label?: string;
  meaning?: string;
  how_to_fill?: string;
  example?: string;
  mistake?: string;
};

type ProductFormState = {
  product_name: string;
  brand: string;
  price_cny: string;
  category_id: string;
  category: string;
  subcategory: string;
  is_custom_subcategory: boolean;
  specifications: JsonObject;
};

type MarketFormState = {
  target_crowd: string;
  crowd_profile: CrowdProfileState;
  crowd_segments: CrowdSegmentState[];
  strategy: string;
  strategies: string[];
  scene: string;
  competitors: ProductItem[];
  sample_size: number;
};

type CrowdProfileState = {
  age_range: string;
  city_tier: string;
  income_level: string;
  life_stage: string;
  price_sensitivity: string;
  feature_priorities: string[];
  channel_preferences: string[];
  purchase_motivations: string[];
  risk_concerns: string[];
  custom_description: string;
};

type CrowdSegmentState = {
  name: string;
  ratio: number;
  is_custom: boolean;
  profile: CrowdProfileState;
};

const emptyProduct: ProductFormState = {
  product_name: "",
  brand: "",
  price_cny: "",
  category_id: "",
  category: "",
  subcategory: "",
  is_custom_subcategory: false,
  specifications: {}
};

const emptyMarket: MarketFormState = {
  target_crowd: "",
  crowd_profile: {
    age_range: "",
    city_tier: "",
    income_level: "",
    life_stage: "",
    price_sensitivity: "medium",
    feature_priorities: [],
    channel_preferences: [],
    purchase_motivations: [],
    risk_concerns: [],
    custom_description: ""
  },
  crowd_segments: [],
  strategy: "",
  strategies: [],
  scene: "",
  competitors: [],
  sample_size: 1000
};

type CustomParamDraft = {
  name: string;
  controlType: string;
  unit: string;
  min: number | null;
  max: number | null;
  step: number | null;
  optionsText: string;
  defaultValue: string;
  defaultWeight: number;
  hint: string;
};

const emptyCustomParamDraft: CustomParamDraft = {
  name: "",
  controlType: "continuousSlider",
  unit: "",
  min: null,
  max: null,
  step: 1,
  optionsText: "",
  defaultValue: "",
  defaultWeight: 3,
  hint: ""
};

type CustomCompetitorDraft = {
  product_name: string;
  brand: string;
  price_cny: string;
};

const emptyCustomCompetitorDraft: CustomCompetitorDraft = {
  product_name: "",
  brand: "",
  price_cny: ""
};

const steps = [
  { key: 1, title: "选择产品", description: "定义品类、价格和核心规格" },
  { key: 2, title: "配置参数", description: "设置目标人群、场景和竞品" },
  { key: 3, title: "运行仿真", description: "提交任务并查看生成进度" },
  { key: 4, title: "查看报告", description: "分析结果、证据和导出分享" }
];

const majorCategories = [...PRODUCT_MAJOR_CATEGORIES, "其他"];
const fallbackCrowds = [
  "年轻白领",
  "价格敏感型家庭用户",
  "品质升级用户",
  "专业/重度用户",
  "银发康养家庭",
  "一线城市高收入用户",
  "下沉市场实用型用户",
  "母婴照护人群",
  "户外露营爱好者",
  "学生与初入职场人群",
  "科技尝鲜用户",
  "企业团购/机构采购",
  "礼品采购人群",
  "健康管理关注者",
  "租房小户型用户",
  "自定义人群"
];

const fallbackStrategies: TemplateItem[] = [
  { id: -1001, name: "性价比策略", description: "突出核心功能与价格优势，适合预算敏感型用户。" },
  { id: -1002, name: "高端品牌策略", description: "强化品牌背书、品质感和售后保障，适合高客单价产品。" },
  { id: -1003, name: "内容种草策略", description: "通过测评、场景化内容和真实案例建立购买信任。" },
  { id: -1004, name: "KOL/KOC 推荐策略", description: "借助达人、垂直博主和真实用户口碑提升转化。" },
  { id: -1005, name: "直播转化策略", description: "用限时权益、演示讲解和客服答疑推动即时成交。" },
  { id: -1006, name: "会员复购策略", description: "通过会员权益、积分和复购券提高留存。" },
  { id: -1007, name: "以旧换新策略", description: "用置换补贴降低升级门槛，适合耐用品和电子产品。" },
  { id: -1008, name: "延保售后保障策略", description: "用延保、上门服务和无忧退换缓解售后顾虑。" },
  { id: -1009, name: "场景套装策略", description: "围绕家庭、办公、户外等场景组合销售，提高客单价。" },
  { id: -1010, name: "线下体验策略", description: "通过门店体验、试用和导购讲解提升信任。" },
  { id: -1011, name: "渠道联合促销策略", description: "联合平台、门店或分销渠道做价格和资源协同。" },
  { id: -1012, name: "企业团购策略", description: "面向企业、机构和批量采购客户提供定制报价与服务。" },
  { id: -1013, name: "私域社群转化策略", description: "通过社群运营、老客推荐和顾问式服务提升转化。" },
  { id: -1014, name: "新品首发尝鲜策略", description: "围绕新品权益、首发礼和尝鲜体验吸引科技敏感人群。" },
  { id: -1015, name: "服务订阅策略", description: "把耗材、保养、内容或增值服务打包成长期权益。" }
];

const ageRangeOptions = ["18-25", "22-35", "26-40", "30-50", "45-60", "55+"].map((value) => ({ value, label: value }));
const cityTierOptions = [
  { value: "tier1", label: "一线/新一线" },
  { value: "tier2", label: "二线城市" },
  { value: "tier3-tier4", label: "三四线城市" },
  { value: "county", label: "县域/乡镇" },
  { value: "lower-tier", label: "下沉市场" }
];
const incomeLevelOptions = [
  { value: "low", label: "低收入/预算有限" },
  { value: "low-middle", label: "中低收入" },
  { value: "middle", label: "中等收入" },
  { value: "middle-high", label: "中高收入" },
  { value: "high", label: "高收入" }
];
const priceSensitivityOptions = [
  { value: "high", label: "高：强关注价格/促销" },
  { value: "medium", label: "中：价格与体验综合权衡" },
  { value: "low", label: "低：更看重品牌/体验" }
];
const defaultFeatureOptions = ["性价比", "续航", "防水", "安全", "品牌", "体验", "便携", "耐用", "售后", "健康", "颜值", "效率"].map((value) => ({ value, label: value }));
const channelPreferenceOptions = ["电商平台", "线下门店", "内容种草", "社交媒体", "KOL/KOC", "机构采购", "私域社群", "亲友推荐"].map((value) => ({ value, label: value }));
const motivationOptions = ["提升效率", "改善体验", "替换旧产品", "送礼", "健康管理", "家庭照护", "尝鲜新技术", "降低成本"].map((value) => ({ value, label: value }));
const riskConcernOptions = ["价格偏高", "质量稳定性", "售后服务", "使用学习成本", "安全风险", "兼容性", "品牌信任不足", "真实效果不确定"].map((value) => ({ value, label: value }));
const customParamControlOptions = [
  { value: "continuousSlider", label: "滑块 + 数值框" },
  { value: "steppedSlider", label: "分段滑块" },
  { value: "discreteSelect", label: "单选/下拉" },
  { value: "multiSelect", label: "多选" },
  { value: "switch", label: "开关" },
  { value: "text", label: "文本输入" }
];
const marketModuleOrder = ["crowd", "scene", "strategy", "competitor", "sample"] as const;
type MarketModuleKey = (typeof marketModuleOrder)[number];
const marketModuleLabels: Record<MarketModuleKey, string> = {
  crowd: "人群",
  scene: "场景",
  strategy: "营销策略",
  competitor: "竞品",
  sample: "样本量"
};

const assistantQuickReplies: Record<AssistantPage, string[]> = {
  step1: ["价格应该怎么填？", "核心参数怎么选？", "普通版和专业版有什么限制？"],
  step2: ["目标人群怎么选？", "价格敏感度是什么意思？", "竞品要选几个？"],
  step3: ["为什么还在生成中？", "预计多久完成？", "运行前要检查什么？"],
  step4: ["购买意愿指数怎么看？", "RAG 证据是什么？", "为什么导出按钮不可用？"]
};

const assistantWelcome: Record<AssistantPage, string> = {
  step1: "我可以协助您确认产品字段和核心参数的填写方式。",
  step2: "我可以协助您判断目标客群、策略、场景和竞品如何配置。",
  step3: "我可以帮您确认运行状态、预计完成时间和运行前检查项。",
  step4: "我可以协助您解读报告指标、证据和导出分享限制。"
};

const priceFieldPattern = /(价格|售价|价位|price|cost)/i;
const paramLabelMap: Record<string, string> = {
  battery: "电池/续航",
  battery_life: "续航能力",
  endurance: "续航能力",
  waterproof: "防水等级",
  water_resistance: "防水等级",
  screen: "屏幕表现",
  display: "屏幕表现",
  weight: "重量",
  motor: "电机性能",
  guardrail: "护栏安全",
  safety: "安全性",
  material: "材质",
  capacity: "容量",
  power: "功率",
  noise: "噪音",
  size: "尺寸",
  color: "颜色",
  connectivity: "连接方式",
  charging: "充电方式"
};

function cleanLabel(value: unknown, fallback: string): string {
  const text = textValue(value).trim();
  if (!text) return fallback;
  const shortened = text.split(/[，。；;:：]/)[0].trim();
  return shortened.length > 18 ? fallback : shortened || fallback;
}

function fieldDisplayName(field?: FieldTemplate | null, fallback?: string): string {
  if (!field) return fallback || "参数";
  const schemaLabel = uiSchema(field)?.label;
  if (schemaLabel) return schemaLabel;
  const mapped = paramLabelMap[field.field_name] || paramLabelMap[field.field_name.toLowerCase()];
  return cleanLabel(field.field_desc, mapped || fallback || field.field_name);
}

function paramDisplayName(name: string, fields: FieldTemplate[]): string {
  const field = fields.find((item) => item.field_name === name);
  if (field) return fieldDisplayName(field, name);
  return paramLabelMap[name] || paramLabelMap[name.toLowerCase()] || name;
}

function uiSchema(field?: FieldTemplate | null): FieldUiSchema | null {
  const schema = field?.ui_schema;
  return schema && typeof schema === "object" && !Array.isArray(schema) ? (schema as FieldUiSchema) : null;
}

function staticParamMatchesBackendField(param: ProductParamTemplate, field: FieldTemplate): boolean {
  const schema = uiSchema(field);
  const candidates = [
    schema?.label,
    cleanLabel(field.field_desc, ""),
    paramLabelMap[field.field_name],
    field.field_name
  ].filter(Boolean);
  const normalizedLabel = normalizeProductSubcategory(param.label);
  return candidates.some((candidate) => normalizeProductSubcategory(String(candidate)) === normalizedLabel);
}

function fieldTemplateFromStaticParam(param: ProductParamTemplate, index: number, backendField?: FieldTemplate): FieldTemplate {
  const numericControl = param.controlType === "continuousSlider" || param.controlType === "steppedSlider";
  return {
    id: backendField?.id ?? -10000 - index,
    field_name: backendField?.field_name || param.name,
    field_type: backendField?.field_type || (numericControl ? "number" : param.controlType === "multiSelect" ? "array" : "string"),
    field_desc: param.hint || backendField?.field_desc || param.label,
    unit: param.unit || backendField?.unit,
    ui_control: param.controlType,
    ui_schema: {
      label: param.label,
      controlType: param.controlType,
      min: param.min,
      max: param.max,
      step: param.step,
      unit: param.unit,
      options: param.options,
      defaultValue: param.defaultValue,
      defaultWeight: param.defaultWeight,
      hint: param.hint
    },
    default_weight: param.defaultWeight,
    is_required: backendField?.is_required || false
  };
}

function fieldTemplateFromCustomParam(
  name: string,
  draft: CustomParamDraft,
  index: number,
  value?: unknown
): FieldTemplate {
  const options = stringArray(draft.optionsText);
  const numericControl = draft.controlType === "continuousSlider" || draft.controlType === "steppedSlider";
  return {
    id: -20000 - index,
    field_name: name,
    field_type: numericControl ? "number" : draft.controlType === "multiSelect" ? "array" : "string",
    field_desc: draft.hint || "手动添加的自定义参数",
    unit: draft.unit,
    ui_control: draft.controlType,
    ui_schema: {
      label: name,
      controlType: draft.controlType,
      min: draft.min ?? undefined,
      max: draft.max ?? undefined,
      step: draft.step ?? undefined,
      unit: draft.unit || undefined,
      options,
      defaultValue: value ?? customDefaultValue(draft),
      defaultWeight: draft.defaultWeight,
      hint: draft.hint || "自定义参数会随当前产品配置一起保存。"
    },
    default_weight: draft.defaultWeight,
    is_required: false
  };
}

function fieldTemplateFromParamSnapshot(item: JsonObject, index: number): FieldTemplate | null {
  const name = textValue(item.raw_name || item.name || item.label).trim();
  if (!name) return null;
  const controlType = textValue(item.controlType || item.control_type || item.ui_control || "text") || "text";
  const options = Array.isArray(item.options) ? item.options.map(textValue).filter(Boolean) : stringArray(item.options);
  const min = Number(item.min);
  const max = Number(item.max);
  const step = Number(item.step);
  const weight = numberValue(item.weight ?? item.default_weight ?? item.defaultWeight, 3);
  return {
    id: -21000 - index,
    field_name: name,
    field_type: controlType === "continuousSlider" || controlType === "steppedSlider" ? "number" : controlType === "multiSelect" ? "array" : "string",
    field_desc: textValue(item.hint || "手动添加的自定义参数"),
    unit: textValue(item.unit),
    ui_control: controlType,
    ui_schema: {
      label: textValue(item.label || name),
      controlType,
      min: Number.isFinite(min) ? min : undefined,
      max: Number.isFinite(max) ? max : undefined,
      step: Number.isFinite(step) ? step : undefined,
      unit: textValue(item.unit) || undefined,
      options,
      defaultValue: item.defaultValue,
      defaultWeight: weight,
      hint: textValue(item.hint || "自定义参数会随当前产品配置一起保存。")
    },
    default_weight: weight,
    is_required: false
  };
}

function customDefaultValue(draft: CustomParamDraft): unknown {
  if (draft.controlType === "multiSelect") return stringArray(draft.defaultValue);
  if (draft.controlType === "switch") {
    const options = stringArray(draft.optionsText);
    return draft.defaultValue || options[0] || "有";
  }
  if (draft.controlType === "continuousSlider" || draft.controlType === "steppedSlider") {
    if (draft.defaultValue.trim()) return numberValue(draft.defaultValue);
    if (typeof draft.min === "number") return draft.min;
    return 0;
  }
  return draft.defaultValue;
}

function matchSubcategoryName(candidate: string | undefined, names: string[]): boolean {
  if (!candidate) return false;
  const normalized = normalizeProductSubcategory(candidate);
  return names.some((name) => normalizeProductSubcategory(name) === normalized);
}

function findBackendCategoryForTemplate(
  categories: Category[],
  category: string,
  subcategory: string,
  template?: ProductSubcategoryTemplate
): Category | undefined {
  const names = [subcategory, template?.subcategory, ...(template?.aliases || [])].filter(Boolean) as string[];
  return categories.find(
    (item) =>
      item.category === category &&
      (matchSubcategoryName(item.subcategory, names) || matchSubcategoryName(item.display_name, names))
  );
}

function schemaOptions(schema?: FieldUiSchema | null): Array<string | number> {
  return Array.isArray(schema?.options) ? schema.options : [];
}

function defaultParamValue(field?: FieldTemplate | null): unknown {
  const schema = uiSchema(field);
  if (!schema || !("defaultValue" in schema)) return "";
  return Array.isArray(schema.defaultValue) ? [...schema.defaultValue] : schema.defaultValue;
}

function defaultParamWeight(field?: FieldTemplate | null): number {
  const schema = uiSchema(field);
  const raw = schema?.defaultWeight ?? field?.default_weight ?? 3;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? Math.min(5, Math.max(1, parsed)) : 3;
}

function numberValue(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function switchChecked(value: unknown, schema?: FieldUiSchema | null): boolean {
  const options = schemaOptions(schema).map(String);
  const onValue = options.find((item) => ["有", "支持", "是", "true"].includes(item)) || options[0] || "有";
  if (typeof value === "boolean") return value;
  if (value === undefined || value === null || value === "") return String(schema?.defaultValue || "") === onValue;
  return String(value) === onValue || ["有", "支持", "是", "true"].includes(String(value));
}

function valueOutsideSchema(value: unknown, schema?: FieldUiSchema | null): boolean {
  if (!schema || typeof schema.min !== "number" || typeof schema.max !== "number") return false;
  const parsed = numberValue(value, Number.NaN);
  return Number.isFinite(parsed) && (parsed < schema.min || parsed > schema.max);
}

function PlatformLogo({ large = false }: { large?: boolean }) {
  return (
    <div className={`logo-mark ${large ? "large" : ""}`} aria-label="智测平台图标">
      <svg width={large ? 48 : 36} height={large ? 48 : 36} viewBox="-5 -10 110 135" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          fill="#2563eb"
          fillRule="evenodd"
          d="m34.59 63.652c-2.5156-0.097656-4.707-0.67969-6.4961-1.7109-1.6445-0.94922-2.9375-2.2578-3.832-3.9102-4.0156 0.76172-7.3867-0.13672-9.8477-1.9531-1.5391-1.1367-2.7148-2.6367-3.4688-4.3125-0.75-1.6836-1.0781-3.5391-0.91797-5.3945 0.26562-3.082 1.8438-6.1602 5.0078-8.4102 0.86719-3.6367 2.7539-6.6133 5.2109-8.7422 2.5859-2.2461 5.8086-3.5508 9.1328-3.6953 2.2852-2.3711 4.7344-3.9453 7.3516-4.7227 2.6523-0.78906 5.4297-0.75 8.3359 0.10938 6.3789-2.7969 12.32-2.5898 17.816 0.61719 5.5352-0.19531 9.6641 1.6797 12.387 5.625 7.1523 1.9883 10.875 6.3555 11.176 13.109 1.1641 1.3047 2.0547 2.8164 2.6523 4.4336 0.90234 2.4297 1.1484 5.0898 0.6875 7.6094-0.46875 2.5586-1.6523 4.9766-3.6055 6.8828-1.0508 1.0234-2.3203 1.8984-3.8203 2.5625-0.13672 0.65234-0.33984 1.293-0.59766 1.918-1.1719 2.8281-3.5156 5.2422-6.4688 6.832-2.9141 1.5664-6.4375 2.3438-10.004 1.9141-0.26562-0.03125-0.53516-0.070312-0.80469-0.11719 0.375 0.72656 0.73828 1.418 1.0859 2.0742 0.17188 0.32422 0.35938 0.62109 0.52734 0.88281 1.1328 1.793 1.8203 2.8789-0.51172 4.7852-1.4688 1.1992-3.0977 1.3281-4.8906 0.38672-1.4102-0.74219-2.9141-2.2383-4.5078-4.4883l-0.027344-0.039062-0.003906 0.003906c-1.6562-2.4883-3.332-4.6406-5.0273-6.457-1.4961-1.6094-3.0039-2.9492-4.5195-4.0234-2.7969 0.61719-5.1797 0.78906-7.1484 0.51172-2.043-0.29297-3.6719-1.0508-4.8711-2.2812zm10.039-33.965c0.23438-0.79297 1.0703-1.2422 1.8633-1.0078 0.79297 0.23437 1.2422 1.0703 1.0078 1.8633-0.86719 2.8906 0.23047 5.3711 1.9648 6.8438 0.69922 0.59375 1.4844 1.0234 2.2773 1.25 0.75391 0.21484 1.5078 0.25391 2.1836 0.082031 1.25-0.32031 2.3008-1.457 2.6562-3.668 0.12891-0.81641 0.89453-1.3711 1.7109-1.2422 0.81641 0.12891 1.3711 0.89453 1.2422 1.7109-0.57812 3.5859-2.5195 5.4883-4.8711 6.0938-1.2031 0.30859-2.4922 0.25391-3.7422-0.10547-1.2109-0.34766-2.3828-0.98047-3.3906-1.8359-0.13281-0.11328-0.26562-0.23047-0.39453-0.35156-1.918 1.1328-3.9258 1.543-5.75 1.3516-1.2695 2.1875-3.4258 3.8594-5.8633 4.8398-1.8438 0.74219-3.8672 1.0938-5.7812 0.98047-0.26563-0.015626-0.53125-0.042969-0.79297-0.074219-1.2031 1.168-2.0195 2.4727-2.4414 3.9102-0.47656 1.625-0.47266 3.4609 0.023438 5.5078 0.625 1.543 1.6641 2.7266 3.0508 3.5234 1.4727 0.85156 3.3594 1.3008 5.5938 1.3242 1.1172-0.12891 2.1211-0.32422 3.0039-0.58594 0.86328-0.25391 1.6172-0.57422 2.2617-0.95312 0.71094-0.42188 1.6289-0.18359 2.0508 0.52734 0.42187 0.71094 0.18359 1.6289-0.52734 2.0508-0.76953 0.45703-1.6484 0.83984-2.6328 1.1523 0.17578 0.035156 0.35547 0.070312 0.54297 0.09375 1.7461 0.24609 3.957 0.050781 6.6328-0.58594l0.015626-0.003906c2.5703-0.71094 5.0586-1.4062 7.4961-2.0898 2.4258-0.68359 4.3867-1.2422 5.8711-1.6719l0.14062-0.035157c1.6836-0.32031 3.0703-0.71094 4.1562-1.168 0.050781-0.027343 0.10547-0.046874 0.16016-0.066406 0.27344-0.12109 0.53125-0.24609 0.76562-0.375 0.94922-0.52734 1.5078-1.0977 1.6758-1.707 0.21484-0.80078 1.0391-1.2695 1.8398-1.0547 0.80078 0.21484 1.2695 1.0391 1.0547 1.8398-0.24609 0.89844-0.75391 1.7031-1.5195 2.4062 1.7773 0.61328 3.5156 1.0195 5.2148 1.2227 2.4883 0.29687 4.8906 0.15625 7.1992-0.42578 1.418-0.53516 2.5898-1.2969 3.5273-2.2109 1.4883-1.4531 2.3945-3.3047 2.75-5.2656 0.36328-2 0.17188-4.1094-0.54688-6.0391-0.51172-1.375-1.2891-2.6602-2.3203-3.7383-1.0234-0.79297-2-1.3242-2.9258-1.5938-0.87891-0.25391-1.7266-0.27734-2.5469-0.066406-0.80078 0.20312-1.6133-0.27734-1.8164-1.0781s0.27734-1.6133 1.0781-1.8164c1.3438-0.34766 2.7188-0.31641 4.1172 0.089844 0.41406 0.12109 0.82812 0.27344 1.2461 0.45703-0.97656-4.0625-4-6.75-9.0742-8.0586-1.6406-0.17188-3.1055-0.074219-4.3984 0.29688-0.92969 0.26562-1.7695 0.67578-2.5273 1.2266 0.5625 0.60156 1.0586 1.2578 1.4844 1.9492 0.56641-0.26562 1.1719-0.46484 1.8125-0.60156 1.1875-0.25391 2.5039-0.28516 3.9414-0.089844 0.82031 0.10938 1.3945 0.86328 1.2812 1.6797-0.10938 0.81641-0.86328 1.3945-1.6797 1.2812-1.0859-0.14453-2.0625-0.12891-2.9219 0.054688-0.43359 0.09375-0.83984 0.22656-1.2148 0.40625 0.5625 1.9336 0.57031 3.9844-0.14062 5.8945-0.30469 0.82031-0.74609 1.6133-1.3281 2.3555-0.51172 0.64844-1.4492 0.75781-2.0977 0.24609-0.64844-0.51172-0.75781-1.4492-0.24609-2.0977 0.38281-0.48438 0.67188-1.0078 0.87109-1.5469 0.52344-1.4023 0.45312-2.9609-0.070313-4.4336-0.53906-1.5273-1.5547-2.9453-2.8945-4.0039-0.69531-0.55078-1.4805-1-2.332-1.3164-0.77344-0.28906-1.168-1.1484-0.87891-1.9219 0.28906-0.77344 1.1484-1.168 1.9219-0.87891 0.75391 0.28125 1.4727 0.64062 2.1406 1.0664 1.1875-1 2.5391-1.7188 4.0586-2.1523 0.71094-0.20312 1.4531-0.34375 2.2344-0.41797-2.1016-1.7812-4.918-2.5742-8.4531-2.3867-3.4219 0.45703-5.8711 1.332-7.3477 2.6172-1.3047 1.1367-1.8242 2.6758-1.5547 4.625 0.11328 0.82031-0.46094 1.5742-1.2773 1.6875-0.82031 0.11328-1.5742-0.45703-1.6875-1.2773-0.41797-3.0195 0.42969-5.4531 2.5469-7.2969 1.1211-0.97266 2.5977-1.7578 4.4336-2.3477-3.7188-1.0664-7.6797-0.63281-11.887 1.2969l-0.03125 0.015625c-0.82812 0.48047-1.4844 1.0352-1.9727 1.6602-0.48437 0.62109-0.8125 1.332-0.98437 2.1328-0.17188 0.80859-0.96484 1.3242-1.7734 1.1523s-1.3242-0.96484-1.1523-1.7773c0.26953-1.2461 0.78906-2.3633 1.5586-3.3516 0.10156-0.12891 0.20703-0.25781 0.31641-0.37891-1.4648-0.15234-2.875-0.027343-4.2305 0.375-2.2148 0.66016-4.3242 2.0664-6.3242 4.2188-1.1523 1.9219-1.7148 3.6211-1.6914 5.0977 0.023438 1.3828 0.58984 2.6211 1.7031 3.7109 0.58984 0.57812 0.59766 1.5273 0.019531 2.1133-0.57812 0.58984-1.5273 0.59766-2.1133 0.019532-1.6953-1.6602-2.5586-3.5938-2.5938-5.7969-0.023438-1.3398 0.27344-2.7539 0.88281-4.2461-1.9062 0.4375-3.7109 1.3594-5.2461 2.6914-2.0625 1.7891-3.6367 4.3242-4.3242 7.4375 0.16797 1.2344 0.52734 2.2266 1.0781 2.9727 0.54688 0.74219 1.3125 1.2695 2.3047 1.582 0.78906 0.25 1.2266 1.0898 0.97656 1.8789-0.25 0.78906-1.0898 1.2266-1.8789 0.97656-1.6055-0.50781-2.8789-1.4023-3.8125-2.6719-0.46094-0.625-0.83203-1.3359-1.1094-2.1289-1.4922 1.5117-2.2617 3.3047-2.418 5.0859-0.11719 1.3594 0.11719 2.7148 0.66016 3.9297 0.54297 1.2188 1.3984 2.3047 2.5195 3.1328 1.7578 1.2969 4.1914 1.9492 7.1523 1.4727-0.10938-0.70312-0.17188-1.3867-0.18359-2.0547-0.78516 0.066406-1.5273 0.046875-2.2188-0.054687-1.2422-0.18359-2.332-0.63281-3.2656-1.3477-0.65625-0.5-0.78125-1.4414-0.28125-2.0977s1.4414-0.78125 2.0977-0.28125c0.52344 0.39844 1.1484 0.65234 1.8828 0.76172 0.625 0.09375 1.3281 0.082031 2.1094-0.03125 0.046875-0.19141 0.097656-0.38281 0.15234-0.57031 0.42969-1.457 1.1406-2.8008 2.1367-4.0234-0.50781-0.25781-0.99219-0.56641-1.4414-0.92578-1.5898-1.2734-2.7266-3.1641-3.0781-5.7539-0.10938-0.82031 0.46484-1.5703 1.2812-1.6797s1.5703 0.46484 1.6797 1.2812c0.23828 1.7539 0.96875 3.0039 1.9883 3.8203 0.68359 0.54688 1.5117 0.91797 2.4141 1.125 0.11328 0.011719 0.22266 0.03125 0.33203 0.066407 0.3125 0.058593 0.63672 0.09375 0.96484 0.11328 1.4805 0.089844 3.0508-0.1875 4.4922-0.76953 1.6211-0.65234 3.0664-1.6797 4.0117-2.9922l-0.066406-0.039062c-0.039062-0.019531-0.074218-0.039063-0.11328-0.058594-0.90625-0.53906-1.6914-1.2695-2.293-2.1719-1-1.4883-1.4961-3.4141-1.2188-5.6484 0.10156-0.82031 0.84766-1.4062 1.668-1.3047s1.4062 0.84766 1.3047 1.668c-0.18359 1.4805 0.11328 2.707 0.72656 3.6211 0.34766 0.51562 0.80469 0.94141 1.3359 1.2578 0.03125 0.019531 0.0625 0.039062 0.089844 0.058594 0.51172 0.28906 1.1055 0.47656 1.7461 0.55859 1.1445 0.14062 2.4258-0.085938 3.6875-0.75-1.1055-2.0078-1.5078-4.5-0.68359-7.2422z"
        />
      </svg>
    </div>
  );
}

function listItems<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object" && "items" in value) {
    const raw = (value as { items?: unknown }).items;
    return Array.isArray(raw) ? (raw as T[]) : [];
  }
  return [];
}

function textValue(value: unknown): string {
  return value === undefined || value === null ? "" : String(value);
}

function normalizedStatus(value: unknown): string {
  return textValue(value).trim().toLowerCase();
}

type StrategyRecommendationView = {
  strategy: string;
  actions: string[];
  expectedImpact: string;
  structured: boolean;
};

function strategyRecommendationText(value: unknown): string {
  if (value === undefined || value === null) return "";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value).trim();
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function strategyRecommendationActions(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(strategyRecommendationText).filter(Boolean);
  const text = strategyRecommendationText(value);
  return text ? [text] : [];
}

function normalizeStrategyRecommendations(value: unknown): StrategyRecommendationView[] {
  const rows = Array.isArray(value) ? value : value ? [value] : [];
  return rows.flatMap((item) => {
    if (item === undefined || item === null || item === "") return [];
    if (typeof item === "object" && !Array.isArray(item)) {
      const data = item as JsonObject;
      const strategy = strategyRecommendationText(data.strategy || data.name || data.title || data.recommendation || data.summary || item);
      return [{
        strategy,
        actions: strategyRecommendationActions(data.actions || data.action_items || data.steps || data.action),
        expectedImpact: strategyRecommendationText(data.expected_impact || data.impact || data.expected_result || data.result),
        structured: true
      }];
    }
    return [{ strategy: strategyRecommendationText(item), actions: [], expectedImpact: "", structured: false }];
  }).filter((item) => item.strategy);
}

function stringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(textValue).filter(Boolean);
  if (typeof value === "string") return value.split(/[，,]/).map((item) => item.trim()).filter(Boolean);
  return [];
}

function emptyCrowdProfile(): CrowdProfileState {
  return {
    age_range: "",
    city_tier: "",
    income_level: "",
    life_stage: "",
    price_sensitivity: "medium",
    feature_priorities: [],
    channel_preferences: [],
    purchase_motivations: [],
    risk_concerns: [],
    custom_description: ""
  };
}

function inferPriceSensitivityFromTags(tags: JsonObject): string {
  const income = textValue(tags.income);
  const name = textValue(tags.name);
  const prefs = stringArray(tags.preferences).join(" ");
  if (income.includes("high") || prefs.includes("品牌") || prefs.includes("体验")) return "low";
  if (income.includes("low") || prefs.includes("性价比") || prefs.includes("价格") || name.includes("价格")) return "high";
  return "medium";
}

function crowdProfileFromTemplate(template?: TemplateItem, previous?: CrowdProfileState): CrowdProfileState {
  const tags = template?.tags || {};
  const base = previous || emptyCrowdProfile();
  return {
    ...base,
    age_range: textValue(tags.age || tags.age_range || base.age_range),
    city_tier: textValue(tags.city || tags.city_tier || base.city_tier),
    income_level: textValue(tags.income || tags.income_level || base.income_level),
    life_stage: textValue(tags.life_stage || tags.usage || tags.buyer || tags.scenario || tags.housing || base.life_stage),
    price_sensitivity: textValue(tags.price_sensitivity || base.price_sensitivity || inferPriceSensitivityFromTags(tags)),
    feature_priorities: stringArray(tags.preferences || tags.feature_priorities).length
      ? stringArray(tags.preferences || tags.feature_priorities)
      : base.feature_priorities,
    channel_preferences: stringArray(tags.channels || tags.channel_preferences).length
      ? stringArray(tags.channels || tags.channel_preferences)
      : base.channel_preferences,
    purchase_motivations: stringArray(tags.motivations || tags.purchase_motivations).length
      ? stringArray(tags.motivations || tags.purchase_motivations)
      : base.purchase_motivations,
    risk_concerns: stringArray(tags.concerns || tags.risk_concerns).length
      ? stringArray(tags.concerns || tags.risk_concerns)
      : base.risk_concerns,
    custom_description: textValue(template?.description || tags.description || base.custom_description)
  };
}

function crowdProfileFromJson(value: unknown): CrowdProfileState {
  const raw = value && typeof value === "object" ? (value as JsonObject) : {};
  return {
    ...emptyCrowdProfile(),
    age_range: textValue(raw.age_range || raw.age),
    city_tier: textValue(raw.city_tier || raw.city),
    income_level: textValue(raw.income_level || raw.income),
    life_stage: textValue(raw.life_stage || raw.occupation || raw.usage),
    price_sensitivity: textValue(raw.price_sensitivity || "medium"),
    feature_priorities: stringArray(raw.feature_priorities || raw.preferences),
    channel_preferences: stringArray(raw.channel_preferences || raw.channels),
    purchase_motivations: stringArray(raw.purchase_motivations || raw.motivations),
    risk_concerns: stringArray(raw.risk_concerns || raw.concerns),
    custom_description: textValue(raw.custom_description || raw.description)
  };
}

function primaryCrowdSegment(segments: CrowdSegmentState[]): CrowdSegmentState | undefined {
  return segments.reduce<CrowdSegmentState | undefined>(
    (best, segment) => (!best || segment.ratio > best.ratio ? segment : best),
    undefined
  );
}

function withLegacyCrowdFields(market: MarketFormState, segments: CrowdSegmentState[]): MarketFormState {
  const primary = primaryCrowdSegment(segments);
  return {
    ...market,
    crowd_segments: segments,
    target_crowd: primary?.name || "",
    crowd_profile: primary?.profile || emptyCrowdProfile()
  };
}

function distributeCrowdRatios(
  segments: CrowdSegmentState[],
  templates: TemplateItem[],
  mode: "template" | "equal" = "template"
): CrowdSegmentState[] {
  if (!segments.length) return [];
  const templateWeightByName = new Map(templates.map((template) => [template.name, Math.max(numberValue(template.default_ratio, 0), 0)]));
  const templateWeights = segments.map((segment) => templateWeightByName.get(segment.name) || 0).filter((value) => value > 0);
  const customWeight = templateWeights.length
    ? templateWeights.reduce((sum, value) => sum + value, 0) / templateWeights.length
    : 1;
  const weights = segments.map((segment) => mode === "equal" ? 1 : (templateWeightByName.get(segment.name) || customWeight));
  const total = weights.reduce((sum, value) => sum + value, 0) || segments.length;
  const distributable = 100 - segments.length;
  const raw = weights.map((weight) => (weight * distributable) / total);
  const ratios = raw.map((value) => 1 + Math.floor(value));
  let remainder = 100 - ratios.reduce((sum, value) => sum + value, 0);
  const order = raw
    .map((value, index) => ({ index, fraction: value - Math.floor(value) }))
    .sort((left, right) => right.fraction - left.fraction || left.index - right.index);
  order.slice(0, remainder).forEach(({ index }) => {
    ratios[index] += 1;
  });
  return segments.map((segment, index) => ({ ...segment, ratio: ratios[index] }));
}

function numberOrNull(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function mergeStrategyTemplates(source: TemplateItem[]): TemplateItem[] {
  const byName = new Map<string, TemplateItem>();
  [...source, ...fallbackStrategies].forEach((item) => {
    const name = textValue(item.name).trim();
    if (!name || byName.has(name)) return;
    byName.set(name, { ...item, name });
  });
  return Array.from(byName.values());
}

function competitorDisplayName(item: ProductItem | JsonObject | undefined): string {
  if (!item) return "";
  return textValue(item.product_name || item.name || item.display_name || item.confirmed_sku || item.title).trim();
}

function competitorPriceValue(item: ProductItem | JsonObject | undefined): number | undefined {
  if (!item) return undefined;
  const raw = item.price_cny ?? item.price ?? item.price_yuan ?? item.reference_price;
  if (raw === undefined || raw === null || raw === "") return undefined;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function normalizeCompetitorItem(item: ProductItem | JsonObject, index = 0): ProductItem | null {
  const productName = competitorDisplayName(item);
  if (!productName) return null;
  const idValue = Number(item.id);
  const normalized: ProductItem = {
    ...item,
    id: Number.isFinite(idValue) ? idValue : -(index + 1),
    product_name: productName
  };
  const price = competitorPriceValue(item);
  if (price !== undefined) normalized.price_cny = price;
  return normalized;
}

function sanitizeCompetitors(items: unknown): ProductItem[] {
  if (!Array.isArray(items)) return [];
  const seen = new Set<string>();
  const result: ProductItem[] = [];
  items.forEach((item, index) => {
    if (!item || typeof item !== "object") return;
    const normalized = normalizeCompetitorItem(item as ProductItem, index);
    if (!normalized) return;
    const key = `${textValue(normalized.id)}|${competitorDisplayName(normalized)}`;
    if (seen.has(key)) return;
    seen.add(key);
    result.push(normalized);
  });
  return result;
}

function normalizeApiDateValue(value: unknown): string {
  const rawValue = String(value).trim();
  const hasExplicitTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(rawValue);
  const looksLikeDateTime = /^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(rawValue);
  if (looksLikeDateTime && !hasExplicitTimezone) {
    return `${rawValue.replace(" ", "T")}Z`;
  }
  return rawValue;
}

function formatDate(value: unknown): string {
  if (!value) return "-";
  const dateText = normalizeApiDateValue(value);
  const date = new Date(dateText);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString("zh-CN", {
        timeZone: "Asia/Shanghai",
        hour12: false
      });
}

function formatTime(value: unknown): string {
  if (!value) return "-";
  const dateText = normalizeApiDateValue(value);
  const date = new Date(dateText);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleTimeString("zh-CN", {
        timeZone: "Asia/Shanghai",
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      });
}

function formatTimeWithOffset(value: unknown, offsetSeconds: number): string {
  if (!value) return "-";
  const dateText = normalizeApiDateValue(value);
  const date = new Date(dateText);
  if (Number.isNaN(date.getTime())) return String(value);
  date.setSeconds(date.getSeconds() + Math.max(0, Math.round(offsetSeconds || 0)));
  return date.toLocaleTimeString("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function formatApproxTimeWithOffset(value: unknown, offsetSeconds: number): string {
  if (!value) return "-";
  const dateText = normalizeApiDateValue(value);
  const date = new Date(dateText);
  if (Number.isNaN(date.getTime())) return String(value);
  date.setSeconds(date.getSeconds() + Math.max(0, Math.round(offsetSeconds || 0)));
  return `${date.toLocaleTimeString("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour12: false,
    hour: "2-digit",
    minute: "2-digit"
  })} 左右`;
}

function formatTimeAfterSeconds(seconds: number): string {
  const date = new Date(Date.now() + Math.max(0, Math.round(seconds || 0)) * 1000);
  return date.toLocaleTimeString("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function formatApproxTimeAfterSeconds(seconds: number): string {
  const date = new Date(Date.now() + Math.max(0, Math.round(seconds || 0)) * 1000);
  return `${date.toLocaleTimeString("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour12: false,
    hour: "2-digit",
    minute: "2-digit"
  })} 左右`;
}

function formatDurationSeconds(value: unknown): string {
  const totalSeconds = Math.max(0, Math.round(Number(value || 0)));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const restMinutes = minutes % 60;
    return `${hours}小时${restMinutes}分钟`;
  }
  if (minutes > 0) return `${minutes}分钟${seconds ? `${seconds}秒` : ""}`;
  return `${seconds}秒`;
}

function sleepMs(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function statusColor(status: string): string {
  const key = normalizedStatus(status);
  if (key === "completed") return "success";
  if (key === "running" || key === "queued" || key === "submitted" || key === "report_waiting" || key === "report_generation_waiting") return "processing";
  if (key === "failed" || key === "cancelled") return "error";
  return "default";
}

function statusLabel(status: string): string {
  const key = normalizedStatus(status);
  const labels: Record<string, string> = {
    draft: "未提交",
    idle: "未提交",
    not_submitted: "未提交",
    waiting_worker: "等待生成",
    submitted: "已提交",
    queued: "等待生成",
    running: "生成中",
    report_waiting: "报告生成中",
    completed: "已完成",
    failed: "生成中断",
    cancelled: "已取消",
    cancel_requested: "取消中"
  };
  if (key === "report_generation_waiting") return labels.report_waiting;
  return labels[key] || textValue(status) || "未知";
}

const businessStageLabels: Record<string, string> = {
  queued: "任务提交",
  start: "开始生成",
  rag: "资料检索",
  agent_generation: "消费者模拟",
  purchase_decision: "购买意愿计算",
  social_propagation: "多轮社交传播",
  aux_validation: "结果复核",
  aggregation: "指标汇总",
  assemble_report: "报告整理",
  report_waiting: "报告生成中",
  report_generation_waiting: "报告生成中",
  completed: "完成"
};

const businessStageMessages: Record<string, string> = {
  queued: "任务已提交，系统将按顺序生成报告",
  start: "系统已开始生成仿真结果",
  rag: "正在整理市场证据与竞品信息",
  agent_generation: "正在生成代表性消费者样本",
  purchase_decision: "正在计算购买意愿与转化判断",
  social_propagation: "正在模拟多轮社交传播影响",
  aux_validation: "正在复核关键结果",
  aggregation: "正在汇总仿真指标",
  assemble_report: "正在整理报告内容",
  report_waiting: "报告正在生成，请稍候",
  report_generation_waiting: "报告正在生成，请稍候",
  completed: "报告已生成完成"
};

const hiddenBusinessLogStages = new Set(["monitor", "queue", "heartbeat", "worker_heartbeat", "task_heartbeat", "orphan_task"]);
const technicalTextPattern = /(Worker|Redis|队列|心跳|运行锁|monitor|Traceback|Exception|IntegrityError|ObjectDeletedError|failed|失败|报错|错误|stuck|lock|orphan)/i;

function businessStageLabel(stage: unknown): string {
  const key = textValue(stage);
  return businessStageLabels[key] || key || "处理中";
}

function businessStageStatus(status: unknown): string {
  const key = textValue(status);
  const labels: Record<string, string> = {
    done: "已完成",
    current: "进行中",
    pending: "待处理",
    failed: "处理中"
  };
  return labels[key] || key || "待处理";
}

function isTechnicalSystemText(value: unknown): boolean {
  return technicalTextPattern.test(textValue(value));
}

function isBusinessLogVisible(item: JsonObject): boolean {
  const stage = textValue(item.stage).toLowerCase();
  if (hiddenBusinessLogStages.has(stage)) return false;
  const level = textValue(item.log_level).toLowerCase();
  const combined = `${textValue(item.stage)} ${textValue(item.message)}`;
  if ((level === "error" || level === "warning") && isTechnicalSystemText(combined)) return false;
  return true;
}

function businessLogMessage(item: JsonObject): string {
  const stage = textValue(item.stage);
  return businessStageMessages[stage] || (isTechnicalSystemText(item.message) ? "系统正在处理当前阶段，请稍候" : textValue(item.message || "阶段处理中"));
}

function userFacingTaskStatus(status: string, messageValue: unknown, errorValue: unknown): string {
  if (status === "failed" && isTechnicalSystemText(`${textValue(messageValue)} ${textValue(errorValue)}`)) return "running";
  return status;
}

function userFacingTaskMessage(status: string, messageValue: unknown, errorValue: unknown): string {
  if (status === "completed") return "任务已完成";
  if (status === "cancelled") return "任务已取消";
  if (status === "failed") return "系统正在整理结果，请稍后刷新查看";
  const raw = textValue(messageValue || errorValue);
  if (!raw || isTechnicalSystemText(raw)) return "系统正在生成仿真报告，请稍候";
  return raw;
}

function diagnosticsVisible(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem("agentsim_show_technical_diagnostics") === "true";
}

function waitForPrintAssets(extraDelayMs = 900): Promise<void> {
  return new Promise((resolve) => {
    const run = async () => {
      try {
        const fonts = (document as Document & { fonts?: { ready?: Promise<unknown> } }).fonts;
        if (fonts?.ready) await fonts.ready;
        const images = Array.from(document.images || []);
        await Promise.all(
          images
            .filter((image) => !image.complete)
            .map(
              (image) =>
                new Promise<void>((done) => {
                  image.addEventListener("load", () => done(), { once: true });
                  image.addEventListener("error", () => done(), { once: true });
                })
            )
        );
        await new Promise<void>((done) => window.requestAnimationFrame(() => window.requestAnimationFrame(() => done())));
        window.setTimeout(resolve, extraDelayMs);
      } catch {
        window.setTimeout(resolve, extraDelayMs);
      }
    };
    run();
  });
}

function projectAction(record: Project): { label: string; step: number } {
  const status = normalizedStatus(record.status);
  if (status === "completed") return { label: "查看报告", step: 4 };
  if (status === "running" || status === "queued" || status === "submitted" || status === "report_waiting" || status === "report_generation_waiting") return { label: "查看进度", step: 3 };
  if (status === "failed" || status === "cancelled") return { label: "修改重试", step: 2 };
  return { label: "继续编辑", step: 1 };
}

function activeProjectId(): string {
  return localStorage.getItem("agentsim_active_project_id") || "";
}

function setActiveProjectId(id: string | number): void {
  localStorage.setItem("agentsim_active_project_id", String(id));
}

function projectPath(step: number, projectId?: string | number): string {
  const id = projectId || activeProjectId();
  return id ? `/step/${step}?project_id=${id}` : "/projects";
}

function projectReadableCode(project?: Project | null): string {
  if (!project?.id) return "-";
  return `SIM-${String(project.id).padStart(5, "0")}`;
}

function uniqueProjectName(baseName: string, projects: Project[]): string {
  const trimmed = baseName.trim() || "复制方案";
  const existing = new Set(projects.map((item) => item.project_name));
  if (!existing.has(trimmed)) return trimmed;
  let index = 1;
  let candidate = `${trimmed}（${index}）`;
  while (existing.has(candidate)) {
    index += 1;
    candidate = `${trimmed}（${index}）`;
  }
  return candidate;
}

function useProjectId(): string {
  const [params] = useSearchParams();
  return params.get("project_id") || activeProjectId();
}

function unwrapReport(project: Project | null): JsonObject {
  return (project?.result_data || {}) as JsonObject;
}

function getChartData(report: JsonObject): JsonObject {
  return ((report.chart_data || {}) as JsonObject) || {};
}

function chartRows(value: unknown): JsonObject[] {
  return Array.isArray(value) ? (value as JsonObject[]) : [];
}

type ChartMissingKind = "crowd" | "strategy" | "competitor" | "social" | "sensitivity" | "price" | "market" | "params" | "model" | "rag";

type ChartMissingInfo = {
  title: string;
  required: string;
  step: string;
  reason: string;
  action: string;
  contact?: boolean;
};

const evidenceContactText = "当前公开资料或平台证据库覆盖较少，可能影响该板块生成。竞品数据不符合您的需要？请联系客服 18960333566。";

const chartMissingConfig: Record<ChartMissingKind, ChartMissingInfo> = {
  crowd: {
    title: "人群分析暂未生成",
    required: "目标客群、客群比例或画像",
    step: "Step2 配置参数",
    reason: "系统未获得足够的人群结构信息，无法拆分不同客群的购买意愿。",
    action: "请回到 Step2 补充目标客群、比例和关键画像后重新运行仿真。"
  },
  strategy: {
    title: "策略分析暂未生成",
    required: "营销策略配置或策略评估结果",
    step: "Step2 配置参数",
    reason: "系统缺少可评估的营销策略，或平台未检索到足够的策略证据。",
    action: "请回到 Step2 选择或补充营销策略；若证据仍偏少，可联系补充资料。",
    contact: true
  },
  competitor: {
    title: "竞品分析暂未生成",
    required: "竞品名称、价格或参数",
    step: "Step2 配置参数",
    reason: "系统缺少有效竞品信息，或当前竞品在公开资料和平台证据库中的覆盖较少。",
    action: "请回到 Step2 补充竞品名称、价格和关键参数后重新运行仿真。",
    contact: true
  },
  social: {
    title: "社交传播暂未生成",
    required: "社交传播轮次结果",
    step: "Step3 运行仿真",
    reason: "本次任务没有生成社交传播轮次数据，旧报告或中断任务常见这种情况。",
    action: "请确认任务完整运行到报告生成阶段；旧项目可重新提交一次仿真。"
  },
  sensitivity: {
    title: "敏感性分析暂未生成",
    required: "产品价格、核心参数或参数权重",
    step: "Step1 选择产品",
    reason: "系统缺少可变动的价格或核心参数，无法计算参数变化对购买意愿的影响。",
    action: "请回到 Step1 补充确定价格、核心参数和权重后重新运行仿真。"
  },
  price: {
    title: "价格敏感曲线暂未生成",
    required: "产品价格或竞品价格",
    step: "Step1 / Step2",
    reason: "系统缺少确定的售价或竞品价格参照，无法判断价格上下浮动对购买意愿的影响。",
    action: "请在 Step1 填写贵公司产品实际售价，并在 Step2 尽量补充竞品价格。"
  },
  market: {
    title: "市场占比暂未生成",
    required: "市场份额或竞品对比",
    step: "Step2 配置参数",
    reason: "系统缺少足够的竞品对比对象，无法进行相对占比估算。",
    action: "请回到 Step2 至少补充 1 个有效竞品，专业版可补充更多竞品提升参考性。",
    contact: true
  },
  params: {
    title: "参数图表暂未生成",
    required: "核心产品参数",
    step: "Step1 选择产品",
    reason: "系统缺少可比较的核心参数，无法生成参数重要性或参数影响图表。",
    action: "请回到 Step1 补充核心规格参数；自定义品类建议至少填写 3 个关键参数。"
  },
  model: {
    title: "购买模型暂未生成完整结果",
    required: "购买决策模型结果",
    step: "Step3 运行仿真",
    reason: "本次任务缺少完整的购买决策模型输出，可能是旧报告、任务中断或证据不足导致。",
    action: "请确认 Step1/Step2 信息完整后重新运行仿真。"
  },
  rag: {
    title: "证据暂未生成",
    required: "当前品类、竞品或市场资料",
    step: "Step1 / Step2",
    reason: "当前公开资料或平台证据库覆盖较少，报告可用依据有限。",
    action: "请补充更明确的品类、竞品名称和关键参数；如资料仍不足，可联系人工补充。",
    contact: true
  }
};

function chartMissingText(kind: ChartMissingKind): string {
  const item = chartMissingConfig[kind];
  return `当前报告缺少生成该板块所需的「${item.required}」信息。缺失原因：${item.reason} 建议：${item.action}${item.contact ? ` ${evidenceContactText}` : ""}`;
}

function ChartMissingNotice({ kind }: { kind: ChartMissingKind }) {
  const item = chartMissingConfig[kind];
  return (
    <Alert
      className="chart-empty-note"
      type="info"
      showIcon
      message={item.title}
      description={chartMissingText(kind)}
    />
  );
}

function chartName(value: unknown, maxLength = 14): string {
  const text = textValue(value);
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function flattenEvidence(report: JsonObject): JsonObject[] {
  const rows: JsonObject[] = [];
  const pushRows = (value: unknown, group: string) => {
    if (Array.isArray(value)) {
      value.forEach((item, index) => {
        if (item && typeof item === "object") rows.push({ group, index, ...(item as JsonObject) });
      });
    } else if (value && typeof value === "object") {
      Object.entries(value as JsonObject).forEach(([key, items]) => pushRows(items, key));
    }
  };
  pushRows(report.evidence_used, "evidence_used");
  pushRows(report.structured_product_evidence, "structured_product_evidence");
  pushRows(report.user_profile_evidence, "user_profile_evidence");
  pushRows(report.market_strategy_evidence, "market_strategy_evidence");
  pushRows(report.rag_evidence, "rag_evidence");
  pushRows(report.data_enrichment_candidates, "data_enrichment_candidates");
  const seen = new Set<string>();
  return rows.filter((row) => {
    const key = `${row.group}-${row.source || row.product_id || row.snippet || row.index}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function ragFinalUsedCount(report: JsonObject): number | null {
  const ragSummary = report.rag_summary;
  if (ragSummary && typeof ragSummary === "object") {
    const total = Number((ragSummary as JsonObject).total_final_used);
    if (Number.isFinite(total)) return total;
  }
  if (Array.isArray(report.rag_evidence)) {
    return report.rag_evidence.filter((item) => item && typeof item === "object").length;
  }
  return null;
}

const CHART_PALETTE = ["#9ec6e1", "#cae0f4", "#dfdfea", "#c9cae7", "#e3d8e6"];
const CHART_TEXT_COLOR = "#475569";
const CHART_AXIS_COLOR = "#94a3b8";
const CHART_GRID_COLOR = "#e8eef7";

function chartAxis(extra: JsonObject = {}): JsonObject {
  return {
    axisLine: { lineStyle: { color: CHART_AXIS_COLOR } },
    axisTick: { lineStyle: { color: CHART_AXIS_COLOR } },
    axisLabel: { color: CHART_TEXT_COLOR },
    splitLine: { lineStyle: { color: CHART_GRID_COLOR } },
    ...extra
  };
}

function chartAxisLabel(extra: JsonObject = {}): JsonObject {
  return {
    color: CHART_TEXT_COLOR,
    interval: 0,
    width: 82,
    overflow: "truncate",
    lineHeight: 14,
    ...extra
  };
}

function chartTooltipFormatter(unit = "") {
  return (params: unknown) => {
    const items = Array.isArray(params) ? params : [params];
    return items
      .map((item) => {
        const row = item as JsonObject;
        const data = (row.data || {}) as JsonObject;
        const name = textValue(data.fullName || row.name || row.axisValue || data.name);
        const value = Array.isArray(data.value) ? data.value.join(" / ") : textValue(data.value ?? row.value);
        const marker = textValue(row.marker);
        return `${marker}${name}${value ? `：${value}${unit}` : ""}`;
      })
      .filter(Boolean)
      .join("<br/>");
  };
}

function chartBase(): JsonObject {
  return {
    color: CHART_PALETTE,
    textStyle: { color: CHART_TEXT_COLOR },
    tooltip: {
      backgroundColor: "rgba(255,255,255,0.96)",
      borderColor: "#d9e4f2",
      textStyle: { color: "#334155" }
    }
  };
}

function pct(value: unknown, digits = 1): string {
  const num = Number(value || 0);
  return `${num.toFixed(digits)}%`;
}

function scorePct(value: unknown, digits = 1): string {
  return `${(Number(value || 0) * 100).toFixed(digits)}%`;
}

function shortText(value: unknown, maxLength = 160): string {
  const text = textValue(value).replace(/\s+/g, " ").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function projectPlan(project: Project | null, user?: User | null, report?: JsonObject): "basic" | "pro" {
  const plan = String(project?.plan_type_used || report?.plan_type_used || getChartData(report || {}).plan_type || user?.plan_type || "basic");
  return plan === "pro" ? "pro" : "basic";
}

function isProjectPro(project: Project | null, user?: User | null, report?: JsonObject): boolean {
  return projectPlan(project, user, report) === "pro";
}

function marketCrowdSummary(market?: JsonObject | null): string {
  const segments = Array.isArray(market?.crowd_segments) ? (market.crowd_segments as JsonObject[]) : [];
  if (segments.length) {
    return segments
      .map((segment) => {
        const name = textValue(segment.name || segment.segment || "目标客群");
        const ratio = Number(segment.ratio);
        return Number.isFinite(ratio) && ratio > 0 ? `${name} ${ratio}%` : name;
      })
      .join("、");
  }
  return textValue(market?.target_crowd || market?.crowd || "-");
}

function strategyName(value: unknown): string {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const data = value as JsonObject;
    return textValue(data.name || data.strategy || data.title || data.label).trim();
  }
  return textValue(value).trim();
}

function marketStrategySummary(market?: JsonObject | null): string {
  const strategies = Array.isArray(market?.strategies) ? (market.strategies as unknown[]) : [];
  const names = strategies.map(strategyName).filter(Boolean);
  if (names.length) return Array.from(new Set(names)).join("、");
  return textValue(market?.strategy || market?.basic_selected_strategy || "-");
}

function Navbar({
  user,
  onLogout,
  onUserChange
}: {
  user: User | null;
  onLogout: () => void;
  onUserChange?: (user: User) => void;
}) {
  const navigate = useNavigate();
  const [switching, setSwitching] = useState(false);

  async function switchDemoAccount(plan: string | number) {
    if (!onUserChange) return;
    const nextPlan = String(plan) === "pro" ? "pro" : "basic";
    if ((user?.plan_type === "pro" ? "pro" : "basic") === nextPlan) return;
    if (!isDemoAccount(user)) {
      Modal.info({
        title: "版本升级说明",
        content: CONTACT_UPGRADE_MESSAGE
      });
      return;
    }
    setSwitching(true);
    try {
      const username = nextPlan === "pro" ? "pro@example" : "normal@example";
      const response = await api.login({ username, password: "123456" });
      setToken(String(response.access_token));
      onUserChange(response.user as User);
      clearActiveProjectCache();
      message.success(`已切换到${nextPlan === "pro" ? "专业版" : "普通版"}测试账号`);
      navigate("/projects");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "测试账号切换失败，请先运行 seed_demo_users.py");
    } finally {
      setSwitching(false);
    }
  }

  return (
    <Header className="navbar">
      <div className="navbar-left" onClick={() => navigate("/projects")}>
        <PlatformLogo />
        <div>
          <div className="logo-title">智测</div>
          <div className="logo-subtitle">基于多agent社会模拟的产品市场接受度仿真平台</div>
        </div>
      </div>
      {user && (
        <Space size={14}>
          <Tooltip title={isDemoAccount(user) ? "测试账号可切换普通版和专业版演示环境；已创建项目的版本不会被转换" : "正式账号升级专业版请联系客服"}>
            <Segmented
              size="small"
              value={user.plan_type === "pro" ? "pro" : "basic"}
              options={[
                { label: "普通版", value: "basic" },
                { label: "专业版", value: "pro" }
              ]}
              disabled={switching}
              onChange={switchDemoAccount}
            />
          </Tooltip>
          <Button icon={<UserOutlined />} onClick={() => navigate("/projects")}>
            个人主页
          </Button>
          <Text type="secondary">{user.username}</Text>
          <Button icon={<LogoutOutlined />} onClick={onLogout}>
            退出
          </Button>
        </Space>
      )}
    </Header>
  );
}

function StepWizard({ active }: { active: number }) {
  const navigate = useNavigate();
  return (
    <div className="steps-container">
      <div className="steps-wrapper">
        {steps.map((step, index) => {
          const complete = active > step.key;
          const current = active === step.key;
          return (
            <button
              key={step.key}
              className={`step-item ${current ? "active" : ""} ${complete ? "completed" : ""}`}
              onClick={() => navigate(projectPath(step.key))}
            >
              <span className="step-circle">{complete ? <CheckCircleOutlined /> : step.key}</span>
              <span className="step-copy">
                <strong>{step.title}</strong>
                <small>{step.description}</small>
              </span>
              {index < steps.length - 1 && <span className="step-connector" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Protected({
  user,
  children
}: {
  user: User | null;
  children: ReactNode;
}) {
  const location = useLocation();
  if (!getToken()) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (!user) return <div className="page-loading">正在读取账号信息...</div>;
  return <>{children}</>;
}

function LoginPage({ onAuthed }: { onAuthed: (user: User) => void }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);

  async function submit(values: { username: string; password: string }) {
    setLoading(true);
    try {
      const response = mode === "login" ? await api.login(values) : await api.register(values);
      setToken(String(response.access_token));
      clearActiveProjectCache();
      onAuthed(response.user as User);
      message.success(mode === "login" ? "登录成功" : "注册成功");
      const target = (location.state as { from?: string } | null)?.from || "/projects";
      navigate(target, { replace: true });
    } catch (error) {
      message.error(error instanceof Error ? error.message : "认证失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <Card className="login-card" bordered={false}>
        <div className="login-brand">
          <PlatformLogo large />
          <Title level={2}>智测</Title>
          <Text>产品市场接受度仿真平台</Text>
        </div>
        <Segmented
          block
          value={mode === "login" ? "登录" : "注册"}
          options={["登录", "注册"]}
          onChange={(value) => setMode(value === "登录" ? "login" : "register")}
        />
        <Form layout="vertical" className="login-form" onFinish={submit}>
          <Form.Item name="username" label="账号" rules={[{ required: true, message: "请输入账号" }]}>
            <Input size="large" placeholder="请输入账号" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password size="large" placeholder="请输入密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" icon={<LoginOutlined />} block size="large" loading={loading}>
            {mode === "login" ? "登录工作台" : "注册并进入"}
          </Button>
          <Text type="secondary" className="demo-account-hint">
            演示账号：pro@example / normal@example，密码均为 123456。注册账号默认使用普通版。
          </Text>
        </Form>
      </Card>
    </main>
  );
}

function AppShell({
  user,
  activeStep,
  children,
  sidebar,
  onLogout,
  onUserChange
}: {
  user: User | null;
  activeStep?: number;
  children: ReactNode;
  sidebar?: ReactNode;
  onLogout: () => void;
  onUserChange?: (user: User) => void;
}) {
  return (
    <Layout className="app-container">
      <Navbar user={user} onLogout={onLogout} onUserChange={onUserChange} />
      {activeStep && <StepWizard active={activeStep} />}
      <Content className="main-layout">
        <section className="content-area">{children}</section>
        {sidebar && <aside className="sidebar-area">{sidebar}</aside>}
      </Content>
    </Layout>
  );
}

function ProjectsPage({ user, onLogout, onUserChange }: { user: User; onLogout: () => void; onUserChange: (user: User) => void }) {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("all");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsDraft, setSettingsDraft] = useState({ full_name: "", email: "", avatar_url: "" });

  const displayName = textValue(user.nickname || user.username);
  const isPro = user.plan_type === "pro";
  const remaining = isPro ? "无限次" : `${Number(user.remaining_simulations ?? user.basic_quota_remaining ?? 0)} 次`;
  const draftProject = projects.find((item) => item.status === "draft");
  const activeTaskProject = projects.find((item) => ["submitted", "queued", "running", "report_waiting"].includes(normalizedStatus(item.status)));
  const latestReport = projects.find((item) => item.status === "completed");
  const statusCounts = {
    running: projects.filter((item) => ["submitted", "queued", "running", "report_waiting"].includes(normalizedStatus(item.status))).length,
    completed: projects.filter((item) => item.status === "completed").length,
    draft: projects.filter((item) => item.status === "draft").length,
  };

  async function loadProjects(page = currentPage, size = pageSize, statusValue = statusFilter) {
    setLoading(true);
    try {
      const query = new URLSearchParams({
        page: String(page),
        page_size: String(size)
      });
      if (statusValue !== "all") query.set("status", statusValue);
      const response = await api.listProjects(query.toString()) as JsonObject;
      setProjects(listItems<Project>(response));
      setTotal(Number(response.total || 0));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "项目加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function createProject(values: { project_name: string }) {
    setCreating(true);
    try {
      const project = (await api.createProject(values.project_name)) as Project;
      setActiveProjectId(project.id);
      navigate(projectPath(1, project.id));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "项目创建失败");
    } finally {
      setCreating(false);
    }
  }

  async function upgradeUser() {
    if (!isDemoAccount(user)) {
      Modal.info({
        title: "版本升级说明",
        content: CONTACT_UPGRADE_MESSAGE
      });
      return;
    }
    setUpgrading(true);
    try {
      const response = await api.login({ username: "pro@example", password: "123456" });
      setToken(String(response.access_token));
      clearActiveProjectCache();
      onUserChange(response.user as User);
      message.success("已切换到专业版测试账号");
      navigate("/projects");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "升级失败");
    } finally {
      setUpgrading(false);
    }
  }

  function openSettings() {
    setSettingsDraft({
      full_name: textValue(user.full_name || user.nickname),
      email: textValue(user.email),
      avatar_url: textValue(user.avatar_url)
    });
    setSettingsOpen(true);
  }

  async function saveSettings() {
    setSettingsSaving(true);
    try {
      const nextUser = (await api.updateProfile({
        full_name: settingsDraft.full_name.trim() || null,
        email: settingsDraft.email.trim() || null,
        avatar_url: settingsDraft.avatar_url.trim() || null
      })) as User;
      onUserChange(nextUser);
      message.success("账号信息已保存");
      setSettingsOpen(false);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "账号信息保存失败");
    } finally {
      setSettingsSaving(false);
    }
  }

  function openProject(record: Project) {
    const action = projectAction(record);
    setActiveProjectId(record.id);
    navigate(projectPath(action.step, record.id));
  }

  async function deleteProject(record: Project) {
    const confirmed = window.confirm(`确认删除项目“${record.project_name}”？已完成的报告和导出任务也会一并清理。`);
    if (!confirmed) return;
    setDeletingId(record.id);
    try {
      await api.deleteProject(record.id);
      if (String(activeProjectId()) === String(record.id)) {
        localStorage.removeItem("agentsim_active_project_id");
      }
      message.success("项目已删除");
      await loadProjects(currentPage, pageSize, statusFilter);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "删除失败");
    } finally {
      setDeletingId(null);
    }
  }

  useEffect(() => {
    loadProjects(currentPage, pageSize, statusFilter);
  }, [currentPage, pageSize, statusFilter]);

  return (
    <AppShell
      user={user}
      onLogout={onLogout}
      onUserChange={onUserChange}
      sidebar={
        <Space direction="vertical" size={16} className="sidebar-stack">
          <Card title="账户状态" className="info-card">
            <Statistic title="当前版本" value={isPro ? "专业版" : "普通版"} />
            <Divider />
            <Statistic title="可用仿真次数" value={remaining} />
            <Alert className="mt-16" type={isPro ? "success" : "info"} showIcon message={isPro ? "专业版可使用完整图表、导出和分享。" : "普通版可运行基础仿真；导出、分享和多竞品需要专业版。"} />
            {!isPro && (
              <Button className="mt-16" type="primary" icon={<CrownOutlined />} loading={upgrading} onClick={upgradeUser} block>
                升级专业版
              </Button>
            )}
            <Button className="mt-16" icon={<SettingOutlined />} onClick={openSettings} block>
              账号设置
            </Button>
          </Card>
          <Card title="快捷入口" className="info-card">
            <Space direction="vertical" className="w-full">
              <Button type="primary" icon={<PlusOutlined />} onClick={() => document.getElementById("new-project-name")?.focus()} block>
                新建仿真
              </Button>
              <Button disabled={!draftProject} onClick={() => draftProject && openProject(draftProject)} block>
                继续草稿
              </Button>
              <Button disabled={!activeTaskProject} onClick={() => activeTaskProject && openProject(activeTaskProject)} block>
                查看运行进度
              </Button>
              <Button disabled={!latestReport} onClick={() => latestReport && openProject(latestReport)} block>
                查看最近报告
              </Button>
            </Space>
          </Card>
        </Space>
      }
    >
      <Card className="info-card dashboard-hero">
        <div className="dashboard-profile">
          <Avatar size={64} src={textValue(user.avatar_url)} icon={<UserOutlined />} />
          <div>
            <Title level={3}>你好，{displayName}</Title>
            <Text type="secondary">在这里管理仿真方案、继续草稿、查看报告和账号版本。</Text>
            <div className="dashboard-tags">
              <Tag color={isPro ? "gold" : "default"}>{isPro ? "专业会员" : "普通会员"}</Tag>
              <Tag color="blue">剩余次数：{remaining}</Tag>
              <Tag color="purple">测试账号可在顶部切换版本</Tag>
            </div>
          </div>
        </div>
        <Row gutter={[16, 16]} className="dashboard-stats">
          <Col xs={24} sm={8}>
            <Statistic title="当前列表项目" value={projects.length} suffix={`/ ${total}`} />
          </Col>
          <Col xs={24} sm={8}>
            <Statistic title="运行中" value={statusCounts.running} />
          </Col>
          <Col xs={24} sm={8}>
            <Statistic title="已完成报告" value={statusCounts.completed} />
          </Col>
        </Row>
      </Card>

      <Card className="info-card">
        <div className="page-title-row">
          <div>
            <Title level={3}>新建仿真</Title>
            <Text type="secondary">创建项目后进入四步工作流，完成产品定义、市场配置、运行和报告查看。</Text>
          </div>
        </div>
        <Form className="new-project-form" layout="inline" onFinish={createProject} initialValues={{ project_name: "新仿真项目" }}>
          <Form.Item name="project_name" rules={[{ required: true, message: "请输入项目名" }]}>
            <Input id="new-project-name" placeholder="项目名称" />
          </Form.Item>
          <Button type="primary" htmlType="submit" icon={<PlusOutlined />} loading={creating}>
            新建项目
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => loadProjects(currentPage, pageSize, statusFilter)}>
            刷新
          </Button>
        </Form>
      </Card>

      <Card
        className="info-card"
        title="历史项目"
        extra={
          <Space>
            <Select
              size="small"
              value={statusFilter}
              onChange={(value) => {
                setStatusFilter(value);
                setCurrentPage(1);
              }}
              options={[
                { value: "all", label: "全部状态" },
                { value: "draft", label: "未提交" },
                { value: "submitted", label: "已提交" },
                { value: "running", label: "运行中" },
                { value: "report_waiting", label: "报告生成中" },
                { value: "completed", label: "已完成" },
                { value: "failed", label: "失败" },
              ]}
            />
            <Button size="small" icon={<ReloadOutlined />} onClick={() => loadProjects(currentPage, pageSize, statusFilter)}>
              刷新
            </Button>
          </Space>
        }
      >
        <Table
          rowKey="id"
          loading={loading}
          dataSource={projects}
          pagination={{
            current: currentPage,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (value) => `共 ${value} 个项目`,
            onChange: (page, size) => {
              setCurrentPage(page);
              setPageSize(size);
            }
          }}
          columns={[
            { title: "项目名称", dataIndex: "project_name" },
            {
              title: "版本",
              dataIndex: "plan_type_used",
              render: (plan: string | undefined) => (
                <Tag color={plan === "pro" ? "gold" : "default"}>{plan === "pro" ? "专业版" : "普通版"}</Tag>
              )
            },
            {
              title: "状态",
              dataIndex: "status",
              render: (status: string) => <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>
            },
            { title: "更新时间", dataIndex: "updated_at", render: formatDate },
            {
              title: "操作",
              render: (_: unknown, record: Project) => (
                <Space>
                  <Button type="link" onClick={() => openProject(record)}>
                    {projectAction(record).label}
                  </Button>
                  <Button danger type="link" icon={<DeleteOutlined />} loading={deletingId === record.id} onClick={() => deleteProject(record)}>
                    删除
                  </Button>
                </Space>
              )
            }
          ]}
        />
      </Card>
      <Modal
        title="账号设置"
        open={settingsOpen}
        okText="保存"
        cancelText="取消"
        confirmLoading={settingsSaving}
        onOk={saveSettings}
        onCancel={() => setSettingsOpen(false)}
      >
        <Form layout="vertical">
          <Form.Item label="显示昵称">
            <Input
              value={settingsDraft.full_name}
              placeholder="请输入希望显示的昵称"
              onChange={(event) => setSettingsDraft((current) => ({ ...current, full_name: event.target.value }))}
            />
          </Form.Item>
          <Form.Item label="邮箱">
            <Input
              value={settingsDraft.email}
              placeholder="请输入联系邮箱"
              onChange={(event) => setSettingsDraft((current) => ({ ...current, email: event.target.value }))}
            />
          </Form.Item>
          <Form.Item label="头像链接">
            <Input
              value={settingsDraft.avatar_url}
              placeholder="可填写图片 URL"
              onChange={(event) => setSettingsDraft((current) => ({ ...current, avatar_url: event.target.value }))}
            />
          </Form.Item>
          <Alert
            type="info"
            showIcon
            message="密码修改和正式账号升级会在后续接入；如需升级专业版，请联系客服 18960333566。"
          />
        </Form>
      </Modal>
    </AppShell>
  );
}

function useProject(projectId: string) {
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(false);

  async function refreshProject() {
    if (!projectId) return;
    setLoading(true);
    try {
      const response = (await api.getProject(projectId)) as Project;
      setProject(response);
      setActiveProjectId(response.id);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "项目加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshProject();
  }, [projectId]);

  return { project, setProject, loading, refreshProject };
}

function AssistantSidebarCard({
  project,
  page,
  context
}: {
  project: Project | null;
  page: AssistantPage;
  context?: JsonObject;
}) {
  const [messages, setMessages] = useState<AssistantMessage[]>([{ role: "assistant", content: assistantWelcome[page] }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [quickReplies, setQuickReplies] = useState<string[]>(assistantQuickReplies[page]);
  const [fieldCards, setFieldCards] = useState<AssistantFieldCard[]>([]);
  const [source, setSource] = useState("fallback");

  useEffect(() => {
    setMessages([{ role: "assistant", content: assistantWelcome[page] }]);
    setInput("");
    setQuickReplies(assistantQuickReplies[page]);
    setFieldCards([]);
    setSource("fallback");
  }, [project?.id, page]);

  async function sendQuestion(question?: string) {
    const content = textValue(question ?? input).trim();
    if (!content || loading) return;
    if (!project?.id) {
      message.warning("请先创建或打开项目");
      return;
    }
    const history = messages.slice(-6);
    setMessages((current) => [...current, { role: "user", content }]);
    setInput("");
    setLoading(true);
    try {
      const response = await api.assistantChat({
        project_id: project.id,
        page,
        message: content,
        history,
        client_context: context || {}
      });
      const nextReply = textValue(response.reply || "我暂时没有找到合适说明。");
      setMessages((current) => [...current, { role: "assistant", content: nextReply }]);
      setQuickReplies(Array.isArray(response.quick_replies) ? response.quick_replies.map(textValue).filter(Boolean) : assistantQuickReplies[page]);
      setFieldCards(Array.isArray(response.field_cards) ? response.field_cards as AssistantFieldCard[] : []);
      setSource(textValue(response.source || "fallback"));
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", content: "助手暂时没有连上。你可以稍后再问，页面原有功能不受影响。" }]);
      message.error(error instanceof Error ? error.message : "助手请求失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card
      title={
        <Space size={6}>
          <RobotOutlined />
          填写助手
        </Space>
      }
      className="info-card assistant-card"
      extra={<Tag color={source === "llm" ? "blue" : "default"}>{source === "llm" ? "智能" : "本地"}</Tag>}
    >
      <Space direction="vertical" size={12} className="w-full">
        <div className="assistant-quick-replies">
          {quickReplies.map((item) => (
            <Button key={item} size="small" onClick={() => sendQuestion(item)} disabled={loading}>
              {item}
            </Button>
          ))}
        </div>
        <div className="assistant-messages">
          {messages.map((item, index) => (
            <div key={`${item.role}-${index}`} className={`assistant-message ${item.role}`}>
              {item.content}
            </div>
          ))}
        </div>
        {fieldCards.map((card, index) => (
          <div key={`${card.key || card.label || "field"}-${index}`} className="assistant-field-card">
            <Text strong>{textValue(card.label || "字段说明")}</Text>
            <Text type="secondary">{textValue(card.meaning)}</Text>
            <Text type="secondary">填写：{textValue(card.how_to_fill || "-")}</Text>
            <Text type="secondary">例子：{textValue(card.example || "-")}</Text>
          </div>
        ))}
        <Input.TextArea
          rows={2}
          maxLength={500}
          value={input}
          placeholder="问我字段含义或怎么填写"
          onChange={(event) => setInput(event.target.value)}
          onPressEnter={(event) => {
            if (!event.shiftKey) {
              event.preventDefault();
              sendQuestion();
            }
          }}
        />
        <Button type="primary" icon={<SendOutlined />} loading={loading} disabled={!input.trim()} onClick={() => sendQuestion()} block>
          发送
        </Button>
      </Space>
    </Card>
  );
}

function ProjectSidebar({
  project,
  extra,
  assistantPage,
  assistantContext
}: {
  project: Project | null;
  extra?: ReactNode;
  assistantPage?: AssistantPage;
  assistantContext?: JsonObject;
}) {
  const navigate = useNavigate();
  const [schemes, setSchemes] = useState<Project[]>([]);
  const [loadingSchemes, setLoadingSchemes] = useState(false);
  const [copyingScheme, setCopyingScheme] = useState(false);

  async function loadSchemes() {
    setLoadingSchemes(true);
    try {
      const response = await api.listProjects("page=1&page_size=8");
      setSchemes(listItems<Project>(response));
    } catch {
      setSchemes([]);
    } finally {
      setLoadingSchemes(false);
    }
  }

  async function createScheme() {
    const name = window.prompt("请输入新方案名称", "新仿真方案");
    if (!name) return;
    try {
      const created = (await api.createProject(name)) as Project;
      setActiveProjectId(created.id);
      message.success("方案已创建");
      navigate(projectPath(1, created.id));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "方案创建失败");
    }
  }

  async function copyCurrentScheme() {
    if (!project?.id) {
      message.warning("请先打开一个方案");
      return;
    }
    const initialName = `${project.project_name || "当前方案"} 副本`;
    const inputName = window.prompt("请输入复制后的方案名称", initialName);
    if (!inputName) return;
    setCopyingScheme(true);
    try {
      const allResponse = await api.listProjects("page=1&page_size=200");
      const allProjects = listItems<Project>(allResponse);
      let finalName = inputName.trim();
      if (allProjects.some((item) => item.project_name === finalName)) {
        const suggestedName = uniqueProjectName(finalName, allProjects);
        const renamed = window.prompt(`方案名称“${finalName}”已存在，请输入新的名称；留空或继续同名将自动使用“${suggestedName}”。`, suggestedName);
        finalName = renamed && renamed.trim() && !allProjects.some((item) => item.project_name === renamed.trim())
          ? renamed.trim()
          : uniqueProjectName((renamed || finalName).trim() || finalName, allProjects);
      }
      const source = (await api.getProject(project.id)) as Project;
      const created = (await api.createProject(finalName)) as Project;
      if (source.product_definition && Object.keys(source.product_definition).length) {
        await api.saveStep1(created.id, source.product_definition);
      }
      if (source.market_config && Object.keys(source.market_config).length) {
        await api.saveStep2(created.id, source.market_config);
      }
      setActiveProjectId(created.id);
      await loadSchemes();
      message.success("当前方案配置已复制");
      const currentStep = assistantPage ? Number(assistantPage.replace("step", "")) || 1 : 1;
      navigate(projectPath(currentStep, created.id));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "复制方案失败");
    } finally {
      setCopyingScheme(false);
    }
  }

  async function deleteScheme(record: Project) {
    const confirmed = window.confirm(`确认删除方案“${record.project_name}”？`);
    if (!confirmed) return;
    try {
      await api.deleteProject(record.id);
      if (String(project?.id) === String(record.id)) {
        localStorage.removeItem("agentsim_active_project_id");
        navigate("/projects");
      } else {
        await loadSchemes();
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "删除失败");
    }
  }

  useEffect(() => {
    loadSchemes();
  }, [project?.id]);

  return (
    <Space direction="vertical" size={16} className="sidebar-stack">
      <Card title="项目概览" className="info-card">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="项目">{project?.project_name || "-"}</Descriptions.Item>
          <Descriptions.Item label="版本">
            <Tag color={project?.plan_type_used === "pro" ? "gold" : "default"}>{project?.plan_type_used === "pro" ? "专业版" : "普通版"}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={statusColor(project?.status || "draft")}>{statusLabel(project?.status || "draft")}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="草稿版本">{project?.draft_version || "-"}</Descriptions.Item>
          <Descriptions.Item label="仿真编号">{projectReadableCode(project)}</Descriptions.Item>
          <Descriptions.Item label="更新时间">{formatDate(project?.updated_at)}</Descriptions.Item>
        </Descriptions>
      </Card>
      {assistantPage && <AssistantSidebarCard project={project} page={assistantPage} context={assistantContext} />}
      <Card
        title="方案管理"
        className="info-card"
        extra={
          <Space size={4}>
            <Tooltip title="新建空方案">
              <Button size="small" icon={<PlusOutlined />} onClick={createScheme} />
            </Tooltip>
            <Tooltip title="复制当前方案">
              <Button size="small" icon={<CopyOutlined />} loading={copyingScheme} onClick={copyCurrentScheme} />
            </Tooltip>
            <Tooltip title="刷新方案列表">
              <Button size="small" icon={<ReloadOutlined />} loading={loadingSchemes} onClick={loadSchemes} />
            </Tooltip>
          </Space>
        }
      >
        <List
          size="small"
          dataSource={schemes}
          locale={{ emptyText: "暂无方案" }}
          renderItem={(item) => (
            <List.Item
              className={String(item.id) === String(project?.id) ? "scheme-item active" : "scheme-item"}
              actions={[
                <Button key="open" size="small" type="link" onClick={() => {
                  setActiveProjectId(item.id);
                  navigate(projectPath(item.status === "completed" ? 4 : 1, item.id));
                }}>
                  打开
                </Button>,
                <Button key="delete" size="small" danger type="link" onClick={() => deleteScheme(item)}>
                  删除
                </Button>
              ]}
            >
              <List.Item.Meta
                title={<Text ellipsis>{item.project_name}</Text>}
                description={
                  <Space size={4} wrap>
                    <Tag color={item.plan_type_used === "pro" ? "gold" : "default"}>{item.plan_type_used === "pro" ? "专业" : "普通"}</Tag>
                    <Tag color={statusColor(item.status)}>{statusLabel(item.status)}</Tag>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
        <Text type="secondary" className="sidebar-note">历史对比入口已保留，正式对比计算后续补齐。</Text>
      </Card>
      <Card title="操作提示" className="info-card">
        <List
          size="small"
          dataSource={["Step1 保存产品定义", "Step2 保存市场配置", "Step3 提交并生成报告", "Step4 查看报告、导出和分享"]}
          renderItem={(item) => <List.Item>{item}</List.Item>}
        />
      </Card>
      {extra}
    </Space>
  );
}

function Step1Product({ user, onLogout, onUserChange }: { user: User; onLogout: () => void; onUserChange: (user: User) => void }) {
  const navigate = useNavigate();
  const projectId = useProjectId();
  const { project, setProject } = useProject(projectId);
  const [categories, setCategories] = useState<Category[]>([]);
  const [fields, setFields] = useState<FieldTemplate[]>([]);
  const [form, setForm] = useState<ProductFormState>(emptyProduct);
  const [paramWeights, setParamWeights] = useState<Record<string, number>>({});
  const [excludedParamNames, setExcludedParamNames] = useState<string[]>([]);
  const [customFields, setCustomFields] = useState<Record<string, FieldTemplate>>({});
  const [customParamOpen, setCustomParamOpen] = useState(false);
  const [customParamDraft, setCustomParamDraft] = useState<CustomParamDraft>(emptyCustomParamDraft);
  const [saving, setSaving] = useState(false);

  const staticTemplate = form.is_custom_subcategory ? undefined : findProductParamTemplate(form.category, form.subcategory);
  const selectedCategoryById = categories.find((category) => String(category.id) === String(form.category_id));
  const selectedCategory = form.is_custom_subcategory
    ? undefined
    : selectedCategoryById || findBackendCategoryForTemplate(categories, form.category, form.subcategory, staticTemplate);
  const currentPlan = projectPlan(project, user);
  const maxParams = currentPlan === "pro" ? 12 : 3;
  const availableMajors = majorCategories;
  const staticSubcategories = productSubcategoriesForMajor(form.category);
  const categorySubcategories = staticSubcategories.length
    ? staticSubcategories.map((subcategory) => ({ value: subcategory, label: subcategory }))
    : categories.filter((item) => item.category === form.category).map((item) => ({ value: item.subcategory || item.display_name, label: item.subcategory || item.display_name }));
  const filteredSubcategories = [
    ...categorySubcategories.filter((item) => item.value !== CUSTOM_SUBCATEGORY_VALUE && item.label !== "其他"),
    { value: CUSTOM_SUBCATEGORY_VALUE, label: "其他" }
  ];
  const staticFields =
    staticTemplate?.params.map((param, index) => {
      const backendField = fields.find((field) => staticParamMatchesBackendField(param, field));
      return fieldTemplateFromStaticParam(param, index, backendField);
    }) || [];
  const templateFieldNames = staticFields.map((field) => field.field_name);
  const visibleFields = (staticFields.length ? staticFields : fields).filter((field) => !priceFieldPattern.test(field.field_name));
  const knownFields = [...visibleFields, ...Object.values(customFields)];
  const customSpecNames = Object.keys(form.specifications).filter((key) => !priceFieldPattern.test(key) && !templateFieldNames.includes(key));
  const selectedSpecNames = staticFields.length
    ? [...templateFieldNames.filter((name) => !excludedParamNames.includes(name)), ...customSpecNames]
    : Object.keys(form.specifications).filter((key) => !priceFieldPattern.test(key) && textValue(form.specifications[key]) !== undefined);
  const enabledSpecNames = selectedSpecNames.filter((_, index) => currentPlan === "pro" || index < maxParams);
  const availableFields = visibleFields.filter((field) => !selectedSpecNames.includes(field.field_name));
  const planLabel = currentPlan === "pro" ? "专业版" : "普通版";
  const limitReached = enabledSpecNames.length >= maxParams;
  const parameterAreaReady = form.category === "其他" || form.is_custom_subcategory ? Boolean(form.subcategory.trim()) : Boolean(form.subcategory || form.category_id);
  const parameterEmptyText = form.category
    ? form.category === "其他" || form.is_custom_subcategory
      ? "填写自定义小品类后，可以继续添加自定义参数。"
      : "选择小品类后自动加载可选参数。"
    : "先选择大品类，再选择小品类。";
  const customCategorySelected = form.category === "其他" || form.is_custom_subcategory;
  const limitedTemplateParams = parameterAreaReady && !customCategorySelected && visibleFields.length > 0 && visibleFields.length < 3;
  const complexityPercent = maxParams ? Math.min(100, Math.round((enabledSpecNames.length / maxParams) * 100)) : 0;
  const estimatedSeconds = Math.max(5, enabledSpecNames.length * 5);

  function hydrate(data: JsonObject) {
    const params = Array.isArray(data.params) ? (data.params as JsonObject[]) : [];
    const specsFromParams: JsonObject = {};
    params.forEach((item) => {
      const rawName = textValue(item.raw_name || item.name);
      const label = textValue(item.label);
      if (rawName) specsFromParams[rawName] = item.value ?? "";
      if (label) specsFromParams[label] = item.value ?? "";
    });
    const specs = { ...specsFromParams, ...(((data.specifications as JsonObject) || {}) as JsonObject) };
    const filteredSpecs = Object.fromEntries(Object.entries(specs).filter(([key]) => !priceFieldPattern.test(key)));
    const weights = Object.fromEntries(
      params
        .filter((item) => textValue(item.raw_name || item.name))
        .map((item) => [textValue(item.raw_name || item.name), numberValue(item.weight, 3)])
    );
    const nextCustomFields = Object.fromEntries(
      params
        .filter((item) => Boolean(item.is_custom))
        .map((item, index) => fieldTemplateFromParamSnapshot(item, index))
        .filter((field): field is FieldTemplate => Boolean(field))
        .map((field) => [field.field_name, field])
    );
    const category = textValue(data.category);
    const categoryId = textValue(data.category_id);
    const subcategory = textValue(data.subcategory);
    const customSubcategory =
      Boolean(data.is_custom_subcategory) ||
      (category !== "其他" && !categoryId && Boolean(subcategory) && !findProductParamTemplate(category, subcategory));
    setForm({
      product_name: textValue(data.product_name || data.name),
      brand: textValue(data.brand),
      price_cny: textValue(data.price_cny),
      category_id: categoryId,
      category,
      subcategory,
      is_custom_subcategory: customSubcategory,
      specifications: filteredSpecs
    });
    setParamWeights(weights);
    setCustomFields(nextCustomFields);
    setExcludedParamNames([]);
  }

  async function loadResources(categoryId?: string) {
    const categoryResponse = await api.categories();
    const nextCategories = listItems<Category>(categoryResponse);
    setCategories(nextCategories);
    if (categoryId) {
      const fieldResponse = await api.fields(categoryId);
      setFields(listItems<FieldTemplate>(fieldResponse));
    }
  }

  useEffect(() => {
    loadResources();
  }, []);

  useEffect(() => {
    if (project?.product_definition) hydrate(project.product_definition);
  }, [project?.id]);

  useEffect(() => {
    if (!form.category_id) {
      setFields([]);
      return;
    }
    loadResources(form.category_id).catch((error) => message.error(error instanceof Error ? error.message : "字段加载失败"));
  }, [form.category_id]);

  function updateSpec(fieldName: string, value: unknown) {
    setForm((current) => ({ ...current, specifications: { ...current.specifications, [fieldName]: value } }));
  }

  function updateWeight(fieldName: string, value: number) {
    setParamWeights((current) => ({ ...current, [fieldName]: value }));
  }

  function confirmClearParams(): boolean {
    if (!selectedSpecNames.length) return true;
    return window.confirm("切换产品品类将清空当前已配置的所有参数，是否继续？");
  }

  function selectMajorCategory(value: string) {
    if (value === form.category) return;
    if (!confirmClearParams()) return;
    setForm((current) => ({
      ...current,
      category: value,
      category_id: "",
      subcategory: value === "其他" ? current.subcategory : "",
      is_custom_subcategory: false,
      specifications: {}
    }));
    setParamWeights({});
    setExcludedParamNames([]);
    setCustomFields({});
    setFields([]);
  }

  function selectSubcategory(subcategory: string) {
    if (subcategory === CUSTOM_SUBCATEGORY_VALUE && form.is_custom_subcategory) return;
    if (!form.is_custom_subcategory && subcategory === form.subcategory) return;
    if (!confirmClearParams()) return;
    if (subcategory === CUSTOM_SUBCATEGORY_VALUE) {
      setForm((current) => ({
        ...current,
        category_id: "",
        subcategory: "",
        is_custom_subcategory: true,
        specifications: {}
      }));
      setParamWeights({});
      setExcludedParamNames([]);
      setCustomFields({});
      setFields([]);
      return;
    }
    const nextTemplate = findProductParamTemplate(form.category, subcategory);
    const next = findBackendCategoryForTemplate(categories, form.category, subcategory, nextTemplate);
    setForm((current) => ({
      ...current,
      category_id: next ? String(next.id) : "",
      category: next?.category || current.category,
      subcategory,
      is_custom_subcategory: false,
      specifications: {}
    }));
    setParamWeights({});
    setExcludedParamNames([]);
    setCustomFields({});
  }

  function addParam(field: FieldTemplate) {
    if (limitReached && !selectedSpecNames.includes(field.field_name)) {
      message.warning(`当前${planLabel}最多添加 ${maxParams} 个产品参数`);
      return;
    }
    setExcludedParamNames((current) => current.filter((name) => name !== field.field_name));
    updateSpec(field.field_name, defaultParamValue(field));
    updateWeight(field.field_name, defaultParamWeight(field));
  }

  function addCustomParam() {
    if (selectedSpecNames.length >= maxParams) {
      message.warning(`当前${planLabel}最多添加 ${maxParams} 个产品参数`);
      return;
    }
    if (currentPlan === "pro") {
      setCustomParamDraft(emptyCustomParamDraft);
      setCustomParamOpen(true);
      return;
    }
    const name = window.prompt("请输入自定义参数名称");
    if (!name) return;
    if (priceFieldPattern.test(name)) {
      message.info("价格已在左侧基础信息中填写，不需要重复添加为参数");
      return;
    }
    updateSpec(name, "");
    updateWeight(name, 3);
  }

  function submitCustomParam() {
    const name = customParamDraft.name.trim();
    if (!name) {
      message.warning("请输入参数名称");
      return;
    }
    if (priceFieldPattern.test(name)) {
      message.info("价格已在左侧基础信息中填写，不需要重复添加为参数");
      return;
    }
    if (selectedSpecNames.includes(name)) {
      message.warning("当前参数名称已存在，请换一个名称");
      return;
    }
    if (selectedSpecNames.length >= maxParams) {
      message.warning(`当前${planLabel}最多添加 ${maxParams} 个产品参数`);
      return;
    }
    if ((customParamDraft.controlType === "continuousSlider" || customParamDraft.controlType === "steppedSlider") && customParamDraft.min !== null && customParamDraft.max !== null && customParamDraft.min >= customParamDraft.max) {
      message.warning("建议范围的最小值需要小于最大值");
      return;
    }
    if (["discreteSelect", "multiSelect"].includes(customParamDraft.controlType) && !stringArray(customParamDraft.optionsText).length) {
      message.warning("请选择类控件需要填写选项，例如：高端,中端,入门");
      return;
    }
    const defaultValue = customDefaultValue(customParamDraft);
    const field = fieldTemplateFromCustomParam(name, customParamDraft, Object.keys(customFields).length, defaultValue);
    setCustomFields((current) => ({ ...current, [name]: field }));
    updateSpec(name, defaultValue);
    updateWeight(name, customParamDraft.defaultWeight);
    setCustomParamOpen(false);
    message.success("自定义参数已添加");
  }

  function removeParam(name: string) {
    if (templateFieldNames.includes(name)) {
      setExcludedParamNames((current) => Array.from(new Set([...current, name])));
    }
    setForm((current) => {
      const next = { ...current.specifications };
      delete next[name];
      return { ...current, specifications: next };
    });
    setParamWeights((current) => {
      const next = { ...current };
      delete next[name];
      return next;
    });
    setCustomFields((current) => {
      const next = { ...current };
      delete next[name];
      return next;
    });
  }

  function paramLocked(name: string): boolean {
    const index = selectedSpecNames.indexOf(name);
    return currentPlan !== "pro" && index >= maxParams;
  }

  function paramValue(name: string, field?: FieldTemplate): unknown {
    return name in form.specifications ? form.specifications[name] : defaultParamValue(field);
  }

  function step1ValidationError(): string | null {
    if (!form.product_name.trim()) return "请先填写产品名称";
    if (!form.category.trim()) return "请先选择产品大品类";
    if (form.category === "其他" || form.is_custom_subcategory) {
      if (!form.subcategory.trim()) return "选择“其他”小品类后，请填写自定义小品类名称";
    } else if (!form.subcategory.trim() && !form.category_id) {
      return "请先选择产品小品类";
    }
    if (form.price_cny.trim() && numberOrNull(form.price_cny) === null) return "价格请填写确定数字，例如 3999";
    return null;
  }

  function ensureStep1Valid(): boolean {
    const error = step1ValidationError();
    if (error) {
      message.warning(error);
      return false;
    }
    return true;
  }

  function jumpToStep2() {
    if (!projectId) return;
    void save();
  }

  async function save() {
    if (!projectId) {
      message.warning("请先创建项目");
      return;
    }
    if (!ensureStep1Valid()) return;
    if (enabledSpecNames.length > maxParams) {
      message.warning(`当前版本最多保存 ${maxParams} 个产品参数`);
      return;
    }
    setSaving(true);
    try {
      const normalizedSpecs = Object.fromEntries(
        selectedSpecNames
          .filter((name) => !priceFieldPattern.test(name))
          .map((name) => {
            const field = knownFields.find((item) => item.field_name === name);
            return [name, paramValue(name, field)];
          })
      );
      const payload = {
        product_name: form.product_name,
        brand: form.brand,
        price_cny: numberOrNull(form.price_cny),
        category_id: form.is_custom_subcategory ? null : selectedCategory?.id || null,
        category: selectedCategory?.category || form.category,
        subcategory: form.is_custom_subcategory ? form.subcategory : selectedCategory?.subcategory || form.subcategory,
        template_subcategory: form.is_custom_subcategory ? form.subcategory : staticTemplate?.subcategory || form.subcategory,
        is_custom_subcategory: form.category === "其他" || form.is_custom_subcategory,
        specifications: normalizedSpecs,
        params: selectedSpecNames
          .filter((name) => !priceFieldPattern.test(name))
          .map((name, index) => {
            const field = knownFields.find((item) => item.field_name === name);
            const preset = visibleFields.some((field) => field.field_name === name);
            const schema = uiSchema(field);
            const value = paramValue(name, field);
            const locked = paramLocked(name);
            const controlType = schema?.controlType || field?.ui_control;
            const outOfRange = valueOutsideSchema(value, schema);
            return {
              id: `param_${index + 1}`,
              name,
              raw_name: name,
              label: paramDisplayName(name, knownFields),
              value,
              enabled: !locked,
              locked,
              is_locked: locked,
              is_preset: preset,
              is_custom: !preset,
              field_type: field?.field_type,
              unit: schema?.unit || field?.unit,
              control_type: controlType,
              controlType,
              min: schema?.min,
              max: schema?.max,
              step: schema?.step,
              options: schemaOptions(schema),
              defaultValue: schema?.defaultValue,
              default_weight: defaultParamWeight(field),
              user_override: outOfRange,
              is_out_of_range: outOfRange,
              weight: paramWeights[name] ?? defaultParamWeight(field)
            };
          })
      };
      const saved = (await api.saveStep1(projectId, payload)) as Project;
      setProject(saved);
      message.success("产品定义已保存");
      navigate(projectPath(2, projectId));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  function renderParamValueControl(name: string, field: FieldTemplate | undefined, label: string, disabled = false) {
    const schema = uiSchema(field);
    const controlType = textValue(schema?.controlType || field?.ui_control).toLowerCase();
    const value = paramValue(name, field);
    const unit = textValue(schema?.unit || field?.unit);
    const options = schemaOptions(schema);
    const warning = valueOutsideSchema(value, schema);
    const numericDefault = numberValue(schema?.defaultValue, typeof schema?.min === "number" ? schema.min : 0);

    if (controlType === "continuousslider" || controlType === "slider") {
      const min = typeof schema?.min === "number" ? schema.min : 0;
      const max = typeof schema?.max === "number" ? schema.max : 100;
      const step = typeof schema?.step === "number" ? schema.step : 1;
      const numeric = numberValue(value, numericDefault);
      return (
        <div className="param-control-stack">
          <div className="param-slider-row">
            <Slider
              className="param-slider"
              min={min}
              max={max}
              step={step}
              value={clamp(numeric, min, max)}
              disabled={disabled}
              onChange={(next) => updateSpec(name, next)}
            />
            <InputNumber
              className={warning ? "param-number-input warning" : "param-number-input"}
              value={Number.isFinite(numeric) ? numeric : undefined}
              step={step}
              disabled={disabled}
              onChange={(next) => updateSpec(name, next ?? "")}
            />
            {unit && <Text type="secondary" className="param-unit">{unit}</Text>}
          </div>
          <Text type={warning ? "warning" : "secondary"} className="param-hint">
            {warning ? `值超出常规范围 (${min}-${max}${unit})，仍可保存。` : schema?.hint || "可直接输入特殊值，滑块仅表示常见建议范围。"}
          </Text>
        </div>
      );
    }

    if (controlType === "steppedslider") {
      const numericOptions = options.map(Number).filter((item) => Number.isFinite(item));
      const min = numericOptions.length ? Math.min(...numericOptions) : 1;
      const max = numericOptions.length ? Math.max(...numericOptions) : 5;
      const marks = Object.fromEntries(numericOptions.map((item) => [item, String(item)]));
      const numeric = numberValue(value, numberValue(schema?.defaultValue, min));
      return (
        <div className="param-control-stack">
          <Slider
            min={min}
            max={max}
            step={1}
            marks={marks}
            value={clamp(numeric, min, max)}
            disabled={disabled}
            onChange={(next) => updateSpec(name, next)}
          />
          <Text type="secondary" className="param-hint">{schema?.hint || "等级滑块会吸附到整数刻度。"}</Text>
        </div>
      );
    }

    if (controlType === "discreteselect") {
      const selectOptions = options.map((item) => ({ value: String(item), label: String(item) }));
      if (selectOptions.length <= 4) {
        return (
          <Radio.Group
            optionType="button"
            buttonStyle="solid"
            value={textValue(value || schema?.defaultValue)}
            options={selectOptions}
            disabled={disabled}
            onChange={(event) => updateSpec(name, event.target.value)}
          />
        );
      }
      return (
        <Select
          value={textValue(value || schema?.defaultValue) || undefined}
          options={selectOptions}
          placeholder={`选择${label}`}
          disabled={disabled}
          onChange={(next) => updateSpec(name, next)}
        />
      );
    }

    if (controlType === "multiselect") {
      return (
        <Checkbox.Group
          className="param-checkbox-group"
          value={stringArray(value || schema?.defaultValue)}
          options={options.map((item) => ({ value: String(item), label: String(item) }))}
          disabled={disabled}
          onChange={(next) => updateSpec(name, next)}
        />
      );
    }

    if (controlType === "switch") {
      const switchOptions = options.map(String);
      const onValue = switchOptions.find((item) => ["有", "支持", "是", "true"].includes(item)) || switchOptions[0] || "有";
      const offValue = switchOptions.find((item) => item !== onValue) || "无";
      return (
        <Space size={10}>
          <Switch
            checked={switchChecked(value, schema)}
            checkedChildren={onValue}
            unCheckedChildren={offValue}
            disabled={disabled}
            onChange={(checked) => updateSpec(name, checked ? onValue : offValue)}
          />
          <Text type="secondary">{switchChecked(value, schema) ? onValue : offValue}</Text>
        </Space>
      );
    }

    if (field?.field_type && ["number", "float", "integer"].includes(field.field_type)) {
      return (
        <Space.Compact className="w-full">
          <InputNumber
            className="w-full"
            value={textValue(value) ? numberValue(value) : undefined}
            placeholder={field.field_desc || `${label}参数值`}
            disabled={disabled}
            onChange={(next) => updateSpec(name, next ?? "")}
          />
          {unit && <Button disabled>{unit}</Button>}
        </Space.Compact>
      );
    }

    return (
      <Input
        value={textValue(value)}
        placeholder={field?.field_desc || `${label}参数值`}
        disabled={disabled}
        onChange={(event) => updateSpec(name, event.target.value)}
      />
    );
  }

  function renderSelectedParams() {
    if (!selectedSpecNames.length) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={parameterAreaReady ? `从上方添加参数，${planLabel}最多 ${maxParams} 个` : parameterEmptyText}
        />
      );
    }
    return (
      <div className="selected-param-list">
        {selectedSpecNames.map((name) => {
          const field = knownFields.find((item) => item.field_name === name);
          const preset = visibleFields.some((field) => field.field_name === name);
          const label = paramDisplayName(name, knownFields);
          const schema = uiSchema(field);
          const locked = paramLocked(name);
          const warning = valueOutsideSchema(paramValue(name, field), schema);
          return (
            <div className={`selected-param-row${warning ? " warning" : ""}${locked ? " locked" : ""}`} key={name}>
              <div className="selected-param-meta">
                <Space size={8} wrap>
                  <Text strong>{label}</Text>
                  <Tag color={preset ? "blue" : "default"}>{preset ? "预设参数" : "自定义参数"}</Tag>
                  {schema?.controlType && <Tag color="geekblue">{schema.controlType}</Tag>}
                  {field?.is_required && <Tag color="red">必填</Tag>}
                  {locked && <Tag icon={<LockOutlined />} color="default">锁定</Tag>}
                </Space>
                <Text type="secondary">{field?.field_desc || field?.field_name || "手动添加的自定义参数"}</Text>
              </div>
              <div className="selected-param-editor">
                {renderParamValueControl(name, field, label, locked)}
                <div className="param-row-actions">
                  <Space size={10} className="param-weight-control">
                    <Text type="secondary">权重</Text>
                    <Slider
                      min={1}
                      max={5}
                      step={1}
                      value={paramWeights[name] ?? defaultParamWeight(field)}
                      disabled={locked}
                      onChange={(next) => updateWeight(name, next)}
                    />
                    <Text strong>{paramWeights[name] ?? defaultParamWeight(field)}</Text>
                  </Space>
                  <Button onClick={() => removeParam(name)} disabled={locked}>移除</Button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  if (!projectId) return <Navigate to="/projects" replace />;

  return (
    <AppShell
      user={user}
      onLogout={onLogout}
      onUserChange={onUserChange}
      activeStep={1}
      sidebar={
        <ProjectSidebar
          project={project}
          assistantPage="step1"
          assistantContext={{
            product_definition: form,
            selected_category: selectedCategory || null,
            field_catalog: knownFields,
            plan_type: currentPlan,
            max_params: maxParams
          }}
          extra={
            <Card title="参数复杂度" className="info-card">
              <Space direction="vertical" size={10} className="w-full">
                <Progress percent={complexityPercent} size="small" strokeColor="#2563eb" />
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="已配置">{selectedSpecNames.length} 个参数</Descriptions.Item>
                  <Descriptions.Item label="可编辑">{enabledSpecNames.length} / {maxParams}</Descriptions.Item>
                  <Descriptions.Item label="版本上限">{planLabel}最多 {maxParams} 个可编辑参数</Descriptions.Item>
                  <Descriptions.Item label="预估耗时">约 {estimatedSeconds} 秒</Descriptions.Item>
                </Descriptions>
                <Text type="secondary" className="sidebar-note">
                  {currentPlan === "pro" ? "专业版可配置更多参数并保留权重。" : "普通版最多保存 3 个参数；已有参数可移除后再更换。"}
                </Text>
              </Space>
            </Card>
          }
        />
      }
    >
      <Card className="info-card" title="Step1 选择产品" extra={<Button onClick={() => navigate("/projects")}>返回项目</Button>}>
        <Space direction="vertical" size={18} className="w-full">
          <section className="step1-section">
            <div className="step1-section-header">
              <div>
                <Text strong>产品基础信息</Text>
                <Text type="secondary">填写产品名称、品类和价格；价格会单独保存，不占用参数名额。</Text>
              </div>
              <Tag color={currentPlan === "pro" ? "gold" : "blue"}>{planLabel}</Tag>
            </div>
            <Form layout="vertical">
              <Row gutter={[16, 0]}>
                <Col xs={24}>
                  <Form.Item label="产品名称" required>
                    <Input
                      value={form.product_name}
                      placeholder="请输入产品名称"
                      onChange={(event) => setForm((current) => ({ ...current, product_name: event.target.value }))}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="品牌">
                    <Input
                      value={form.brand}
                      placeholder="请输入品牌，可选"
                      onChange={(event) => setForm((current) => ({ ...current, brand: event.target.value }))}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="价格（元）">
                    <Input
                      value={form.price_cny}
                      placeholder="请输入参考价格"
                      onChange={(event) => setForm((current) => ({ ...current, price_cny: event.target.value }))}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="大品类" required>
                    <Select
                      showSearch
                      value={form.category || undefined}
                      placeholder="请选择产品大类"
                      optionFilterProp="label"
                      onChange={selectMajorCategory}
                      options={availableMajors.map((item) => ({ value: item, label: item }))}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  {form.category === "其他" ? (
                    <Form.Item label="自定义小品类" required>
                      <Input
                        value={form.subcategory}
                        placeholder="请输入自定义小品类"
                        onChange={(event) => setForm((current) => ({ ...current, subcategory: event.target.value }))}
                      />
                    </Form.Item>
                  ) : (
                    <>
                      <Form.Item label="小品类" required>
                        <Select
                          showSearch
                          value={form.is_custom_subcategory ? CUSTOM_SUBCATEGORY_VALUE : form.subcategory || undefined}
                          placeholder={form.category ? "请选择产品小品类" : "请先选择产品大类"}
                          optionFilterProp="label"
                          disabled={!form.category}
                          onChange={selectSubcategory}
                          options={filteredSubcategories}
                        />
                      </Form.Item>
                      {form.is_custom_subcategory && (
                        <Form.Item label="自定义小品类" required>
                          <Input
                            value={form.subcategory}
                            placeholder="请输入自定义小品类名称"
                            onChange={(event) => setForm((current) => ({ ...current, subcategory: event.target.value }))}
                          />
                        </Form.Item>
                      )}
                    </>
                  )}
                </Col>
              </Row>
            </Form>
          </section>

          <section className="step1-section">
            <div className="step1-section-header">
              <div>
                <Text strong>{form.subcategory ? `功能与参数配置（${form.subcategory}）` : "功能与参数配置"}</Text>
                <Text type="secondary">
                  {currentPlan === "pro" ? `专业版最多添加 ${maxParams} 个参数。` : "普通版最多添加 3 个参数，升级专业版可配置更多参数。"}
                </Text>
              </div>
              <Space size={8} wrap>
                <Tag color={currentPlan === "pro" ? "gold" : "default"}>可编辑 {enabledSpecNames.length} / {maxParams}</Tag>
                {selectedSpecNames.length > enabledSpecNames.length && <Tag icon={<LockOutlined />}>锁定 {selectedSpecNames.length - enabledSpecNames.length}</Tag>}
                {!parameterAreaReady && <Tag>待选择小品类</Tag>}
              </Space>
            </div>

            {!parameterAreaReady ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={parameterEmptyText} />
            ) : (
              <Space direction="vertical" size={14} className="w-full">
                {limitReached && (
                  <Alert
                    type={currentPlan === "pro" ? "warning" : "info"}
                    showIcon
                    icon={currentPlan === "pro" ? undefined : <LockOutlined />}
                    message={`${planLabel}参数数量已达上限`}
                    description={currentPlan === "pro" ? `当前最多添加 ${maxParams} 个参数。` : "普通版最多添加 3 个参数，已有参数仍可编辑或移除。"}
                  />
                )}
                {customCategorySelected && (
                  <Alert
                    type="info"
                    showIcon
                    message="自定义小品类提示"
                    description="自定义小品类不会自动匹配完整参数模板。建议至少补充 3 个核心参数，并在 Step2 补充竞品名称和价格，否则后续参数影响、竞品分析和价格敏感图表可能只展示说明。"
                  />
                )}
                {limitedTemplateParams && (
                  <Alert
                    type="info"
                    showIcon
                    message="当前参数模板较少"
                    description="该小品类可用模板参数较少。您可以继续添加自定义参数，帮助系统生成更完整的参数影响和敏感性分析。"
                  />
                )}
                {form.category !== "其他" && !form.is_custom_subcategory && visibleFields.length > 0 && (
                  <div className="param-pool-panel">
                    <div className="param-pool-header">
                      <Text strong>可选参数</Text>
                      <Text type="secondary">来自当前小品类字段模板，点击即可加入配置。</Text>
                    </div>
                    <div className="param-pool">
                      {availableFields.length ? (
                        availableFields.map((field) => (
                          <Button key={field.id} size="small" onClick={() => addParam(field)} disabled={limitReached}>
                            + {fieldDisplayName(field)}
                          </Button>
                        ))
                      ) : (
                        <Text type="secondary">可选参数已全部添加</Text>
                      )}
                    </div>
                  </div>
                )}
                {form.category !== "其他" && !visibleFields.length && (
                  <Alert type="info" showIcon message="当前小品类暂无字段模板，可继续使用自定义参数。" />
                )}
                <Button size="small" onClick={addCustomParam} disabled={limitReached}>
                  + 自定义参数
                </Button>
                {renderSelectedParams()}
              </Space>
            )}
          </section>
        </Space>
        <Divider />
        <Space>
          <Button type="primary" size="large" onClick={save} loading={saving}>
            保存并进入 Step2
          </Button>
          <Button onClick={jumpToStep2}>跳转 Step2</Button>
        </Space>
      </Card>
      <Modal
        title="添加自定义参数"
        open={customParamOpen}
        onCancel={() => setCustomParamOpen(false)}
        onOk={submitCustomParam}
        okText="添加参数"
        cancelText="取消"
        width={680}
      >
        <Form layout="vertical" className="custom-param-form">
          <Row gutter={12}>
            <Col xs={24} md={12}>
              <Form.Item label="参数名称" required>
                <Input
                  value={customParamDraft.name}
                  placeholder="例如：特殊传感器精度"
                  onChange={(event) => setCustomParamDraft((current) => ({ ...current, name: event.target.value }))}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="控件类型" required>
                <Select
                  value={customParamDraft.controlType}
                  options={customParamControlOptions}
                  onChange={(value) => setCustomParamDraft((current) => ({ ...current, controlType: value }))}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="单位">
                <Input
                  value={customParamDraft.unit}
                  placeholder="如 mAh、kg、小时"
                  onChange={(event) => setCustomParamDraft((current) => ({ ...current, unit: event.target.value }))}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="默认权重">
                <InputNumber
                  min={1}
                  max={5}
                  step={1}
                  className="w-full"
                  value={customParamDraft.defaultWeight}
                  onChange={(value) => setCustomParamDraft((current) => ({ ...current, defaultWeight: clamp(numberValue(value, 3), 1, 5) }))}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="默认值">
                {customParamDraft.controlType === "continuousSlider" || customParamDraft.controlType === "steppedSlider" ? (
                  <InputNumber
                    className="w-full"
                    value={customParamDraft.defaultValue ? numberValue(customParamDraft.defaultValue) : undefined}
                    onChange={(value) => setCustomParamDraft((current) => ({ ...current, defaultValue: value === null || value === undefined ? "" : String(value) }))}
                  />
                ) : (
                  <Input
                    value={customParamDraft.defaultValue}
                    placeholder={customParamDraft.controlType === "multiSelect" ? "多个默认值用逗号分隔" : "可选"}
                    onChange={(event) => setCustomParamDraft((current) => ({ ...current, defaultValue: event.target.value }))}
                  />
                )}
              </Form.Item>
            </Col>
            {(customParamDraft.controlType === "continuousSlider" || customParamDraft.controlType === "steppedSlider") && (
              <>
                <Col xs={24} md={8}>
                  <Form.Item label="建议最小值">
                    <InputNumber
                      className="w-full"
                      value={customParamDraft.min ?? undefined}
                      onChange={(value) => setCustomParamDraft((current) => ({ ...current, min: value === null || value === undefined ? null : numberValue(value) }))}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} md={8}>
                  <Form.Item label="建议最大值">
                    <InputNumber
                      className="w-full"
                      value={customParamDraft.max ?? undefined}
                      onChange={(value) => setCustomParamDraft((current) => ({ ...current, max: value === null || value === undefined ? null : numberValue(value) }))}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} md={8}>
                  <Form.Item label="步长">
                    <InputNumber
                      className="w-full"
                      min={0.0001}
                      value={customParamDraft.step ?? undefined}
                      onChange={(value) => setCustomParamDraft((current) => ({ ...current, step: value === null || value === undefined ? null : numberValue(value, 1) }))}
                    />
                  </Form.Item>
                </Col>
              </>
            )}
            {["discreteSelect", "multiSelect", "switch", "steppedSlider"].includes(customParamDraft.controlType) && (
              <Col xs={24}>
                <Form.Item label={customParamDraft.controlType === "steppedSlider" ? "刻度/选项" : "选项"}>
                  <Input
                    value={customParamDraft.optionsText}
                    placeholder={customParamDraft.controlType === "switch" ? "有,无" : "用逗号分隔，例如：旗舰,中端,入门"}
                    onChange={(event) => setCustomParamDraft((current) => ({ ...current, optionsText: event.target.value }))}
                  />
                </Form.Item>
              </Col>
            )}
            <Col xs={24}>
              <Form.Item label="小字提示">
                <Input.TextArea
                  rows={2}
                  value={customParamDraft.hint}
                  placeholder="例如：范围只是常见建议值，特殊产品可以直接输入超出范围的数值。"
                  onChange={(event) => setCustomParamDraft((current) => ({ ...current, hint: event.target.value }))}
                />
              </Form.Item>
            </Col>
          </Row>
          <Alert
            type="info"
            showIcon
            message="自定义参数会作为当前产品配置保存，不会覆盖模板参数。滑块范围只是建议值，特殊产品可以输入超出范围的数值。"
          />
        </Form>
      </Modal>
    </AppShell>
  );
}

function Step2Market({ user, onLogout, onUserChange }: { user: User; onLogout: () => void; onUserChange: (user: User) => void }) {
  const navigate = useNavigate();
  const projectId = useProjectId();
  const { project, setProject } = useProject(projectId);
  const [market, setMarket] = useState<MarketFormState>(emptyMarket);
  const [crowds, setCrowds] = useState<TemplateItem[]>([]);
  const [strategies, setStrategies] = useState<TemplateItem[]>([]);
  const [scenes, setScenes] = useState<TemplateItem[]>([]);
  const [competitors, setCompetitors] = useState<ProductItem[]>([]);
  const [loadingCompetitors, setLoadingCompetitors] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activeCrowdName, setActiveCrowdName] = useState("");
  const [activeMarketModule, setActiveMarketModule] = useState<MarketModuleKey>("crowd");
  const [customCompetitorOpen, setCustomCompetitorOpen] = useState(false);
  const [customCompetitorDraft, setCustomCompetitorDraft] = useState<CustomCompetitorDraft>(emptyCustomCompetitorDraft);
  const currentPlan = projectPlan(project, user);
  const isProPlan = currentPlan === "pro";
  const crowdOptions = useMemo(() => {
    const names = new Set<string>();
    crowds.forEach((item) => names.add(item.name));
    fallbackCrowds.forEach((item) => names.add(item));
    return Array.from(names).map((name) => ({ value: name, label: name }));
  }, [crowds]);
  const selectedStrategies = isProPlan
    ? stringArray(market.strategies)
    : stringArray(market.strategy || market.strategies[0]).slice(0, 1);

  function hydrate(data: JsonObject) {
    const legacyName = textValue(data.target_crowd || data.crowd);
    const legacyProfile = crowdProfileFromJson(data.crowd_profile);
    const rawSegments = Array.isArray(data.crowd_segments) ? data.crowd_segments : [];
    const crowdSegments = rawSegments
      .filter((item): item is JsonObject => Boolean(item && typeof item === "object"))
      .map((item) => ({
        name: textValue(item.name || item.segment),
        ratio: Math.max(1, Math.round(numberValue(item.ratio, 0))),
        is_custom: Boolean(item.is_custom),
        profile: crowdProfileFromJson(item.profile)
      }))
      .filter((item) => item.name);
    const normalizedSegments = crowdSegments.length
      ? crowdSegments
      : legacyName
        ? [{ name: legacyName, ratio: 100, is_custom: false, profile: legacyProfile }]
        : [];
    const primary = primaryCrowdSegment(normalizedSegments);
    setMarket({
      target_crowd: primary?.name || legacyName,
      crowd_profile: primary?.profile || legacyProfile,
      crowd_segments: normalizedSegments,
      strategy: textValue(data.strategy || stringArray(data.strategies)[0]),
      strategies: stringArray(data.strategies).length ? stringArray(data.strategies) : stringArray(data.strategy),
      scene: textValue(data.scene),
      competitors: sanitizeCompetitors(data.competitors),
      sample_size: numberValue(data.sample_size, projectPlan(project, user) === "pro" ? 10000 : 1000)
    });
    setActiveCrowdName(normalizedSegments[0]?.name || "");
  }

  function updateCrowdProfile(patch: Partial<CrowdProfileState>) {
    setMarket((current) => {
      const segments = current.crowd_segments.map((segment) => (
        segment.name === activeCrowdName ? { ...segment, profile: { ...segment.profile, ...patch } } : segment
      ));
      return withLegacyCrowdFields(current, segments);
    });
  }

  function updateCrowdSelection(values: string[]) {
    const uniqueNames = Array.from(new Set(values.map(textValue).filter(Boolean)));
    const limit = projectPlan(project, user) === "pro" ? uniqueNames.length : 3;
    if (uniqueNames.length > limit) message.info("普通版最多选择 3 类目标客群");
    const allowedNames = uniqueNames.slice(0, limit);
    setMarket((current) => {
      const existing = new Map(current.crowd_segments.map((segment) => [segment.name, segment]));
      const segments = allowedNames.map((name) => {
        const saved = existing.get(name);
        if (saved) return saved;
        const template = crowds.find((item) => item.name === name);
        return {
          name,
          ratio: 1,
          is_custom: !template,
          profile: crowdProfileFromTemplate(template)
        };
      });
      return withLegacyCrowdFields(current, distributeCrowdRatios(segments, crowds));
    });
    if (!allowedNames.includes(activeCrowdName)) setActiveCrowdName(allowedNames[0] || "");
  }

  function updateCrowdRatio(name: string, ratio: number | null) {
    setMarket((current) => withLegacyCrowdFields(
      current,
      current.crowd_segments.map((segment) => (
        segment.name === name ? { ...segment, ratio: clamp(Math.round(numberValue(ratio, segment.ratio)), 1, 100) } : segment
      ))
    ));
  }

  function redistributeCrowds(mode: "template" | "equal") {
    setMarket((current) => withLegacyCrowdFields(current, distributeCrowdRatios(current.crowd_segments, crowds, mode)));
  }

  function productQuery(limit: number, offset: number) {
    const categoryId = project?.product_definition?.category_id;
    const category = textValue(project?.product_definition?.category);
    const subcategory = textValue(project?.product_definition?.subcategory);
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (categoryId) params.set("category_id", String(categoryId));
    if (!categoryId && category) params.set("category", category);
    if (!categoryId && subcategory) params.set("subcategory", subcategory);
    return params.toString();
  }

  async function loadCompetitorProducts(loadAll = false): Promise<ProductItem[]> {
    setLoadingCompetitors(true);
    try {
      const pageSize = loadAll ? 100 : 20;
      let offset = 0;
      let total = 0;
      const rows: ProductItem[] = [];
      do {
        const productResponse = (await api.products(productQuery(pageSize, offset))) as JsonObject;
        const items = listItems<ProductItem>(productResponse);
        total = Number(productResponse.total || items.length);
        rows.push(...items);
        offset += pageSize;
      } while (loadAll && rows.length < total && offset < 2000);
      const normalizedRows = sanitizeCompetitors(rows);
      setCompetitors(normalizedRows);
      return normalizedRows;
    } finally {
      setLoadingCompetitors(false);
    }
  }

  async function loadResources() {
    const templateResponse = (await api.marketTemplates()) as JsonObject;
    setCrowds(listItems<TemplateItem>(templateResponse.crowd));
    setStrategies(mergeStrategyTemplates(listItems<TemplateItem>(templateResponse.strategy)));
    setScenes(listItems<TemplateItem>(templateResponse.scene));
    await loadCompetitorProducts(projectPlan(project, user) === "pro");
  }

  useEffect(() => {
    if (project?.market_config) hydrate(project.market_config);
    if (project) loadResources().catch((error) => message.error(error instanceof Error ? error.message : "市场模板加载失败"));
  }, [project?.id]);

  function step2ValidationError(): { message: string; module: MarketModuleKey } | null {
    if (!market.crowd_segments.length) return { message: "请至少选择 1 类目标客群", module: "crowd" };
    const ratioTotal = market.crowd_segments.reduce((sum, segment) => sum + segment.ratio, 0);
    if (ratioTotal !== 100) return { message: "目标客群比例合计必须为 100%", module: "crowd" };
    if (!market.scene.trim()) return { message: "请先选择使用场景", module: "scene" };
    if (!selectedStrategies.length) return { message: "请先选择营销策略", module: "strategy" };
    if (!sanitizeCompetitors(market.competitors).length) return { message: "请至少选择或添加 1 个竞品", module: "competitor" };
    return null;
  }

  function ensureStep2Valid(): boolean {
    const error = step2ValidationError();
    if (!error) return true;
    setActiveMarketModule(error.module);
    message.warning(error.message);
    return false;
  }

  function openCustomCompetitor() {
    setCustomCompetitorDraft(emptyCustomCompetitorDraft);
    setCustomCompetitorOpen(true);
  }

  function submitCustomCompetitor() {
    const productName = customCompetitorDraft.product_name.trim();
    if (!productName) {
      message.warning("请输入竞品名称");
      return;
    }
    const priceText = customCompetitorDraft.price_cny.trim();
    const price = priceText ? Number(priceText) : undefined;
    if (priceText && !Number.isFinite(price)) {
      message.warning("竞品价格请填写数字，或留空");
      return;
    }
    const duplicate = market.competitors.some((item) => competitorDisplayName(item) === productName);
    if (duplicate) {
      message.warning("该竞品已在已选列表中");
      return;
    }
    const customCompetitor: ProductItem = {
      id: -Date.now(),
      product_name: productName,
      brand: customCompetitorDraft.brand.trim(),
      price_cny: price,
      is_custom: true,
      source: "custom"
    };
    setCompetitors((current) => sanitizeCompetitors([customCompetitor, ...current]));
    setMarket((current) => {
      const currentSelected = sanitizeCompetitors(current.competitors);
      const next = sanitizeCompetitors([...(isProPlan ? currentSelected : []), customCompetitor]);
      if (!isProPlan && currentSelected.length) {
        message.info("普通版最多保留 1 个竞品，自定义竞品已替换当前选择");
      }
      return { ...current, competitors: isProPlan ? next : next.slice(-1) };
    });
    setCustomCompetitorOpen(false);
    message.success("自定义竞品已添加");
  }

  async function save() {
    if (!projectId) return;
    if (!ensureStep2Valid()) return;
    setSaving(true);
    try {
      const normalizedCompetitors = sanitizeCompetitors(market.competitors);
      const competitorsForSave = currentPlan === "pro" ? normalizedCompetitors : normalizedCompetitors.slice(0, 1);
      const strategyList = currentPlan === "pro"
        ? (selectedStrategies.length ? selectedStrategies : stringArray(market.strategy))
        : stringArray(market.strategy || market.strategies[0]).slice(0, 1);
      const sampleSize = currentPlan === "pro" ? clamp(numberValue(market.sample_size, 10000), 1000, 10000) : 1000;
      const crowdSegmentsForSave = market.crowd_segments.map((segment) => ({
        ...segment,
        profile: currentPlan === "pro"
          ? segment.profile
          : {
              price_sensitivity: segment.profile.price_sensitivity || "medium",
              feature_priorities: segment.profile.feature_priorities.slice(0, 3),
              custom_description: segment.profile.custom_description
            }
      }));
      const primarySegment = primaryCrowdSegment(market.crowd_segments);
      const primarySavedSegment = crowdSegmentsForSave.find((segment) => segment.name === primarySegment?.name);
      const saved = (await api.saveStep2(projectId, {
        ...market,
        target_crowd: primarySegment?.name || "",
        crowd_profile: primarySavedSegment?.profile || {},
        crowd_segments: crowdSegmentsForSave,
        strategy: strategyList[0] || market.strategy,
        strategies: strategyList,
        sample_size: sampleSize,
        competitors: competitorsForSave
      })) as Project;
      setProject(saved);
      message.success("市场配置已保存");
      navigate(projectPath(3, projectId));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  const competitorColumns = [
    { title: "品牌", dataIndex: "brand" },
    { title: "产品", dataIndex: "product_name" },
    {
      title: "价格",
      dataIndex: "price_cny",
      render: (value: number | undefined) => (value ? `￥${value}` : <Text type="secondary">缺失</Text>)
    }
  ];
  const crowdRatioTotal = market.crowd_segments.reduce((sum, segment) => sum + segment.ratio, 0);
  const activeCrowdSegment = market.crowd_segments.find((segment) => segment.name === activeCrowdName) || market.crowd_segments[0];
  const activeCrowdProfile = activeCrowdSegment?.profile || emptyCrowdProfile();
  const completionItems = [
    {
      key: "crowd" as MarketModuleKey,
      label: marketModuleLabels.crowd,
      done: Boolean(market.crowd_segments.length && crowdRatioTotal === 100)
    },
    { key: "scene" as MarketModuleKey, label: marketModuleLabels.scene, done: Boolean(market.scene) },
    { key: "strategy" as MarketModuleKey, label: marketModuleLabels.strategy, done: selectedStrategies.length > 0 },
    { key: "competitor" as MarketModuleKey, label: marketModuleLabels.competitor, done: market.competitors.length > 0 },
    { key: "sample" as MarketModuleKey, label: marketModuleLabels.sample, done: Boolean(isProPlan ? market.sample_size : true) }
  ];
  const completionPercent = Math.round((completionItems.filter((item) => item.done).length / completionItems.length) * 100);
  const selectedCompetitorsForPreview = sanitizeCompetitors(market.competitors);
  const missingCompetitorPriceCount = selectedCompetitorsForPreview.filter((item) => competitorPriceValue(item) === undefined).length;
  const reportCompletenessTips = [
    !market.crowd_segments.length || crowdRatioTotal !== 100 ? "缺少目标客群或比例会影响人群分析和购买意愿分客群图表。" : "",
    !selectedStrategies.length ? "缺少营销策略会影响策略 ROI、渠道贡献和策略证据板块。" : "",
    !selectedCompetitorsForPreview.length ? "缺少竞品会影响市场占比、竞品分析和价格敏感曲线。" : "",
    missingCompetitorPriceCount > 0 ? "竞品价格缺失时仍可保存，但价格覆盖率、价格敏感曲线和竞品对比可能不完整。" : ""
  ].filter(Boolean);

  async function selectAllCompetitors() {
    if (!isProPlan) {
      message.info("普通版最多选择 1 个竞品");
      return;
    }
    try {
      const rows = await loadCompetitorProducts(true);
      setMarket((current) => ({ ...current, competitors: rows }));
      message.success(`已选择当前品类/筛选结果内 ${rows.length} 个竞品`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "竞品加载失败");
    }
  }

  if (!projectId) return <Navigate to="/projects" replace />;

  return (
    <AppShell
      user={user}
      onLogout={onLogout}
      onUserChange={onUserChange}
      activeStep={2}
      sidebar={
        <ProjectSidebar
          project={project}
          assistantPage="step2"
          assistantContext={{
            product_definition: project?.product_definition || {},
            market_config: market,
            crowd_templates: crowds,
            strategy_templates: strategies,
            scene_templates: scenes,
            competitor_count: market.competitors.length,
            plan_type: currentPlan
          }}
        />
      }
    >
      <Card className="info-card" title="Step2 配置参数" extra={<Button onClick={() => navigate(projectPath(1, projectId))}>返回 Step1</Button>}>
        <Row gutter={[16, 16]} className="market-config-grid">
          <Col xs={24} lg={17}>
            <Tabs
              activeKey={activeMarketModule}
              onChange={(key) => setActiveMarketModule(key as MarketModuleKey)}
              items={[
                {
                  key: "crowd",
                  label: "人群",
                  children: (
                    <Form layout="vertical" className="market-module-form">
                      <Form.Item label="目标人群" required>
                        <Select
                          mode="tags"
                          value={market.crowd_segments.map((segment) => segment.name)}
                          placeholder="选择或输入目标人群"
                          onChange={(value) => updateCrowdSelection(stringArray(value))}
                          options={crowdOptions}
                        />
                      </Form.Item>
                      <Alert
                        className="mb-16"
                        type={crowdRatioTotal === 100 ? "success" : "warning"}
                        showIcon
                        message={`当前比例合计 ${crowdRatioTotal}%${crowdRatioTotal === 100 ? "" : "，保存前需要调整为 100%"}`}
                        action={
                          <Space wrap>
                            <Button size="small" onClick={() => redistributeCrowds("template")}>按模板分配</Button>
                            <Button size="small" onClick={() => redistributeCrowds("equal")}>平均分配</Button>
                          </Space>
                        }
                      />
                      <div className="crowd-ratio-list">
                        {market.crowd_segments.map((segment) => (
                          <div key={segment.name} className={`crowd-ratio-row${activeCrowdSegment?.name === segment.name ? " active" : ""}`}>
                            <Button type="link" className="crowd-ratio-name" onClick={() => setActiveCrowdName(segment.name)}>
                              {segment.name}
                            </Button>
                            <Slider min={1} max={100} value={segment.ratio} onChange={(value) => updateCrowdRatio(segment.name, value)} />
                            <InputNumber
                              min={1}
                              max={100}
                              addonAfter="%"
                              value={segment.ratio}
                              onChange={(value) => updateCrowdRatio(segment.name, value)}
                            />
                            <Tooltip title="移除客群">
                              <Button
                                aria-label={`移除${segment.name}`}
                                danger
                                type="text"
                                icon={<DeleteOutlined />}
                                onClick={() => updateCrowdSelection(market.crowd_segments.filter((item) => item.name !== segment.name).map((item) => item.name))}
                              />
                            </Tooltip>
                          </div>
                        ))}
                        {!market.crowd_segments.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请选择至少一类目标客群" />}
                      </div>
                      {activeCrowdSegment && (
                        <div className="crowd-profile-panel">
                          <Title level={5}>{isProPlan ? "目标人群画像" : "基础人群画像"}：{activeCrowdSegment.name}</Title>
                        <Form.Item label="价格敏感度">
                          <Select
                            value={activeCrowdProfile.price_sensitivity || "medium"}
                            onChange={(value) => updateCrowdProfile({ price_sensitivity: value })}
                            options={priceSensitivityOptions}
                          />
                        </Form.Item>
                        <Form.Item label={`功能偏好${isProPlan ? "" : "（最多 3 个）"}`}>
                          <Select
                            mode="tags"
                            value={activeCrowdProfile.feature_priorities}
                            placeholder="选择或输入关注功能"
                            onChange={(value) => {
                              const next = stringArray(value);
                              if (!isProPlan && next.length > 3) message.info("普通版最多选择 3 个功能偏好");
                              updateCrowdProfile({ feature_priorities: isProPlan ? next : next.slice(0, 3) });
                            }}
                            options={defaultFeatureOptions}
                          />
                        </Form.Item>
                        {isProPlan && (
                          <>
                            <Row gutter={8}>
                              <Col span={12}>
                                <Form.Item label="年龄段">
                                  <Select allowClear value={activeCrowdProfile.age_range || undefined} onChange={(value) => updateCrowdProfile({ age_range: value || "" })} options={ageRangeOptions} />
                                </Form.Item>
                              </Col>
                              <Col span={12}>
                                <Form.Item label="城市层级">
                                  <Select allowClear value={activeCrowdProfile.city_tier || undefined} onChange={(value) => updateCrowdProfile({ city_tier: value || "" })} options={cityTierOptions} />
                                </Form.Item>
                              </Col>
                            </Row>
                            <Row gutter={8}>
                              <Col span={12}>
                                <Form.Item label="收入水平">
                                  <Select allowClear value={activeCrowdProfile.income_level || undefined} onChange={(value) => updateCrowdProfile({ income_level: value || "" })} options={incomeLevelOptions} />
                                </Form.Item>
                              </Col>
                              <Col span={12}>
                                <Form.Item label="职业/家庭阶段">
                                  <Input value={activeCrowdProfile.life_stage} placeholder="如：育儿家庭、康养照护、户外重度用户" onChange={(event) => updateCrowdProfile({ life_stage: event.target.value })} />
                                </Form.Item>
                              </Col>
                            </Row>
                            <Form.Item label="渠道偏好">
                              <Select mode="tags" value={activeCrowdProfile.channel_preferences} onChange={(value) => updateCrowdProfile({ channel_preferences: stringArray(value) })} options={channelPreferenceOptions} />
                            </Form.Item>
                            <Form.Item label="购买动机">
                              <Select mode="tags" value={activeCrowdProfile.purchase_motivations} onChange={(value) => updateCrowdProfile({ purchase_motivations: stringArray(value) })} options={motivationOptions} />
                            </Form.Item>
                            <Form.Item label="风险顾虑">
                              <Select mode="tags" value={activeCrowdProfile.risk_concerns} onChange={(value) => updateCrowdProfile({ risk_concerns: stringArray(value) })} options={riskConcernOptions} />
                            </Form.Item>
                          </>
                        )}
                        <Form.Item label="补充描述">
                          <Input.TextArea rows={3} value={activeCrowdProfile.custom_description} placeholder="补充这个人群的消费心理、典型场景或特殊要求" onChange={(event) => updateCrowdProfile({ custom_description: event.target.value })} />
                        </Form.Item>
                        </div>
                      )}
                    </Form>
                  )
                },
                {
                  key: "scene",
                  label: "场景",
                  children: (
                    <Form layout="vertical" className="market-module-form">
                      <Form.Item label="使用场景" required>
                        <Select
                          value={market.scene || undefined}
                          placeholder="选择场景"
                          onChange={(value) => setMarket((current) => ({ ...current, scene: value }))}
                          options={scenes.map((item) => ({ value: item.name, label: item.name }))}
                        />
                      </Form.Item>
                      <Alert type="info" showIcon message="场景会影响用户关注点和购买动机，例如通勤、家庭照护、户外露营、礼品采购等。" />
                    </Form>
                  )
                },
                {
                  key: "strategy",
                  label: "营销策略",
                  children: (
                    <Form layout="vertical" className="market-module-form">
                      <Form.Item label={isProPlan ? "营销策略组合" : "营销策略"} required>
                        {isProPlan ? (
                          <Select
                            mode="multiple"
                            value={selectedStrategies}
                            placeholder="选择一个或多个策略"
                            onChange={(values) => setMarket((current) => ({ ...current, strategies: stringArray(values), strategy: textValue(values[0]) }))}
                            options={strategies.map((item) => ({ value: item.name, label: item.name }))}
                          />
                        ) : (
                          <Select
                            value={market.strategy || undefined}
                            placeholder="选择策略"
                            onChange={(value) => setMarket((current) => ({ ...current, strategy: value, strategies: [value] }))}
                            options={strategies.map((item) => ({ value: item.name, label: item.name }))}
                          />
                        )}
                      </Form.Item>
                      <Alert
                        type={isProPlan ? "success" : "info"}
                        showIcon
                        message={isProPlan ? "专业版可保存多策略组合；报告会按组合语境分析。" : "普通版保留单策略，方便快速完成基础仿真。"}
                      />
                    </Form>
                  )
                },
                {
                  key: "competitor",
                  label: "竞品",
                  children: (
                    <Card
                      size="small"
                      title="竞品选择"
                      className="nested-card"
                      extra={
                        <Space>
                          <Button size="small" icon={<PlusOutlined />} onClick={openCustomCompetitor}>
                            自定义竞品
                          </Button>
                          {isProPlan && (
                            <Button size="small" onClick={selectAllCompetitors} loading={loadingCompetitors}>
                              全选当前品类竞品
                            </Button>
                          )}
                          <Button size="small" onClick={() => setMarket((current) => ({ ...current, competitors: [] }))}>
                            清空选择
                          </Button>
                        </Space>
                      }
                    >
                      <Alert
                        className="mb-16"
                        type={isProPlan ? "success" : "info"}
                        showIcon
                        message={isProPlan ? "专业版可全选当前品类/筛选结果内竞品；页面图表显示 Top N 汇总，表格和导出保留全量分析。" : "普通版最多选择 1 个竞品；升级后新建项目可使用多竞品分析。"}
                      />
                      <Table
                        rowKey="id"
                        size="small"
                        loading={loadingCompetitors}
                        dataSource={competitors}
                        columns={competitorColumns}
                        pagination={{ pageSize: 8, showTotal: (total) => `共 ${total} 个候选竞品` }}
                        rowSelection={{
                          selectedRowKeys: market.competitors.map((item) => item.id),
                          preserveSelectedRowKeys: true,
                          onChange: (_, rows) => {
                            const selectedRows = sanitizeCompetitors(rows as ProductItem[]);
                            if (!isProPlan && selectedRows.length > 1) message.info("普通版最多选择 1 个竞品");
                            setMarket((current) => ({ ...current, competitors: isProPlan ? selectedRows : selectedRows.slice(0, 1) }));
                          }
                        }}
                      />
                    </Card>
                  )
                },
                {
                  key: "sample",
                  label: "样本量",
                  children: (
                    <Form layout="vertical" className="market-module-form">
                      <Form.Item label="仿真样本量">
                        <div className="sample-size-control">
                          <Slider
                            min={1000}
                            max={10000}
                            step={500}
                            value={isProPlan ? clamp(numberValue(market.sample_size, 10000), 1000, 10000) : 1000}
                            disabled={!isProPlan}
                            onChange={(value) => setMarket((current) => ({ ...current, sample_size: value }))}
                          />
                          <InputNumber
                            min={1000}
                            max={10000}
                            step={500}
                            value={isProPlan ? clamp(numberValue(market.sample_size, 10000), 1000, 10000) : 1000}
                            disabled={!isProPlan}
                            onChange={(value) => setMarket((current) => ({ ...current, sample_size: numberValue(value, 10000) }))}
                          />
                        </div>
                      </Form.Item>
                      <Alert
                        type={isProPlan ? "success" : "info"}
                        showIcon
                        message={isProPlan ? "样本量越大，仿真覆盖更充分，但运行时间也会更长。" : "普通版样本量固定为 1000；专业版可在 1000-10000 之间调整。"}
                      />
                    </Form>
                  )
                }
              ]}
            />
          </Col>
          <Col xs={24} lg={7}>
            <Card size="small" className="nested-card market-completion-card" title="完成度">
              <Progress percent={completionPercent} size="small" strokeColor="#2563eb" />
              <div className="market-module-list">
                {completionItems.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className={`market-module-item${activeMarketModule === item.key ? " active" : ""}`}
                    onClick={() => setActiveMarketModule(item.key)}
                  >
                    <span>{item.label}</span>
                    <Tag color={item.done ? "success" : "default"}>{item.done ? "已配置" : "待完善"}</Tag>
                  </button>
                ))}
              </div>
              {reportCompletenessTips.length > 0 && (
                <Alert
                  className="mt-16"
                  type="info"
                  showIcon
                  message="报告完整性提示"
                  description={
                    <Space direction="vertical" size={4}>
                      {reportCompletenessTips.map((tip) => <Text key={tip}>{tip}</Text>)}
                    </Space>
                  }
                />
              )}
            </Card>
            <Card size="small" className="nested-card mt-16" title="已选预览">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="人群">{market.crowd_segments.length ? `${market.crowd_segments.length} 类` : "-"}</Descriptions.Item>
                <Descriptions.Item label="场景">{market.scene || "-"}</Descriptions.Item>
                <Descriptions.Item label="策略">{selectedStrategies.length ? selectedStrategies.join("、") : "-"}</Descriptions.Item>
                <Descriptions.Item label="竞品">{selectedCompetitorsForPreview.length} 个</Descriptions.Item>
                <Descriptions.Item label="样本量">{isProPlan ? numberValue(market.sample_size, 10000) : 1000}</Descriptions.Item>
              </Descriptions>
              {market.crowd_segments.length > 0 && (
                <List
                  size="small"
                  className="selected-crowd-list"
                  dataSource={market.crowd_segments}
                  renderItem={(item) => (
                    <List.Item>
                      <Text>{item.name}</Text>
                      <Tag color="blue">{item.ratio}%</Tag>
                    </List.Item>
                  )}
                />
              )}
              {selectedCompetitorsForPreview.length > 0 && (
                <List
                  size="small"
                  className="selected-competitor-list"
                  dataSource={selectedCompetitorsForPreview.slice(0, 5)}
                  renderItem={(item) => (
                    <List.Item>
                      <Text ellipsis>{[textValue(item.brand), competitorDisplayName(item)].filter(Boolean).join(" ")}</Text>
                    </List.Item>
                  )}
                />
              )}
              {selectedCompetitorsForPreview.length > 5 && <Text type="secondary">还有 {selectedCompetitorsForPreview.length - 5} 个竞品未展开显示。</Text>}
              {missingCompetitorPriceCount > 0 && (
                <Alert
                  className="mt-16"
                  type="warning"
                  showIcon
                  message={`有 ${missingCompetitorPriceCount} 个竞品未填写价格`}
                  description={`仍可继续保存，但价格敏感曲线、价格覆盖率和竞品价格结论可能不完整。竞品数据不符合您的需要？请联系客服 18960333566。`}
                />
              )}
            </Card>
          </Col>
        </Row>
        <Divider />
        <Space>
          <Button type="primary" size="large" onClick={save} loading={saving}>
            保存并进入 Step3
          </Button>
          <Button onClick={() => void save()} loading={saving}>跳转 Step3</Button>
        </Space>
      </Card>
      <Modal
        title="添加自定义竞品"
        open={customCompetitorOpen}
        onCancel={() => setCustomCompetitorOpen(false)}
        onOk={submitCustomCompetitor}
        okText="添加竞品"
        cancelText="取消"
      >
        <Form layout="vertical">
          <Form.Item label="竞品名称" required>
            <Input
              value={customCompetitorDraft.product_name}
              placeholder="请输入竞品产品名称"
              onChange={(event) => setCustomCompetitorDraft((current) => ({ ...current, product_name: event.target.value }))}
            />
          </Form.Item>
          <Form.Item label="品牌">
            <Input
              value={customCompetitorDraft.brand}
              placeholder="可选"
              onChange={(event) => setCustomCompetitorDraft((current) => ({ ...current, brand: event.target.value }))}
            />
          </Form.Item>
          <Form.Item label="价格（元）">
            <InputNumber
              min={0}
              precision={2}
              className="w-full"
              value={customCompetitorDraft.price_cny ? Number(customCompetitorDraft.price_cny) : null}
              placeholder="可留空"
              onChange={(value) => setCustomCompetitorDraft((current) => ({ ...current, price_cny: value === null || value === undefined ? "" : String(value) }))}
            />
          </Form.Item>
          <Alert
            type="info"
            showIcon
            message="如果暂时没有价格，可以先留空；只要有竞品名称，系统会保留该竞品，并在后续分析中提示价格证据不足。"
          />
        </Form>
      </Modal>
    </AppShell>
  );
}

function Step3Simulate({ user, onLogout, onUserChange }: { user: User; onLogout: () => void; onUserChange: (user: User) => void }) {
  const navigate = useNavigate();
  const projectId = useProjectId();
  const { project, setProject, refreshProject } = useProject(projectId);
  const [task, setTask] = useState<JsonObject>({});
  const [logs, setLogs] = useState<JsonObject[]>([]);
  const [queueStatus, setQueueStatus] = useState<JsonObject>({});
  const [runningAction, setRunningAction] = useState("");

  function displayTaskStatus(): string {
    const raw = String(task.status || "");
    if (raw) return raw;
    if (project?.status === "submitted") return "submitted";
    if (project?.status === "running") return "running";
    if (project?.status === "report_waiting") return "report_waiting";
    if (project?.status === "completed") return "completed";
    if (project?.status === "failed" || project?.status === "cancelled") return String(project?.status);
    return "not_submitted";
  }

  function totalQueueLength(): number {
    const lengths = queueStatus.lengths as JsonObject | undefined;
    if (!lengths) return 0;
    return Object.values(lengths).reduce<number>((sum, value) => sum + Number(value || 0), 0);
  }

  async function refreshProgress() {
    if (!projectId) return;
    const response = (await api.progress(projectId)) as JsonObject;
    setProject(response.project as Project);
    setTask((response.task as JsonObject) || {});
    try {
      setQueueStatus((await api.queueStatus()) as JsonObject);
    } catch {
      setQueueStatus({});
    }
    const logResponse = (await api.logs(projectId, 80)) as JsonObject;
    setLogs(listItems<JsonObject>(logResponse));
  }

  useEffect(() => {
    refreshProgress().catch(() => undefined);
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    const status = String(task.status || project?.status || "");
    if (status !== "running" && status !== "queued" && status !== "retrying" && status !== "report_waiting" && status !== "cancel_requested") return;
    const timer = window.setInterval(() => {
      refreshProgress().catch((error) => message.error(error instanceof Error ? error.message : "进度刷新失败"));
    }, 1800);
    return () => window.clearInterval(timer);
  }, [projectId, task.status, project?.status]);

  async function submitAndRun() {
    if (!projectId) return;
    setRunningAction("run");
    try {
      await api.submit(projectId);
      const response = (await api.run(projectId)) as JsonObject;
      setProject(response.project as Project);
      setTask((response.task as JsonObject) || {});
      message.success("任务已提交，系统会按顺序自动开始");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "启动失败");
    } finally {
      setRunningAction("");
    }
  }

  async function cancelTask() {
    if (!projectId) return;
    setRunningAction("cancel");
    try {
      const response = (await api.cancel(projectId)) as JsonObject;
      setProject(response.project as Project);
      setTask((response.task as JsonObject) || {});
      message.info("已请求取消");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "取消失败");
    } finally {
      setRunningAction("");
    }
  }

  const stages = listItems<JsonObject>(task.stages);
  const percent = clamp(numberValue(task.percent, project?.status === "completed" ? 100 : 0), 0, 100);
  const currentStatus = normalizedStatus(displayTaskStatus());
  const queueDiagnostics = (task.queue_diagnostics || {}) as JsonObject;
  const currentPlan = projectPlan(project, user);
  const workerHeartbeatCount = Number(queueStatus.worker_heartbeat_count ?? queueDiagnostics.worker_heartbeat_count ?? 0);
  const taskHeartbeatCount = Number(queueStatus.task_heartbeat_count ?? queueStatus.heartbeat_count ?? 0);
  const reportWaiting = Boolean(task.report_waiting) || ["report_generation_waiting", "report_waiting"].includes(normalizedStatus(task.stage));
  const remainingSeconds = Number(task.remaining_seconds);
  const targetDurationSeconds = Number(task.target_duration_seconds);
  const estimatedCompletedAt = textValue(task.estimated_completed_at);
  const backendQueueEtaSeconds = Number(task.queue_eta_seconds ?? queueDiagnostics.queue_eta_seconds);
  const hasBackendQueueEta =
    ["queued", "submitted", "retrying"].includes(currentStatus) &&
    Number.isFinite(backendQueueEtaSeconds) &&
    backendQueueEtaSeconds > 0;
  const queuePosition = Number(queueDiagnostics.queue_position);
  const queuedAheadCount = currentStatus === "queued"
    ? Number.isFinite(queuePosition) && queuePosition >= 0
      ? Math.max(0, queuePosition)
      : Math.max(0, totalQueueLength() - 1)
    : 0;
  const activeTaskAheadCount =
    currentStatus === "queued" &&
    (Number(queueStatus.project_lock_count || 0) > 0 || (Boolean(queueDiagnostics.in_queue) && Boolean(queueDiagnostics.worker_online) && queuedAheadCount === 0))
      ? 1
      : 0;
  const estimatedSingleTaskSeconds = Number.isFinite(targetDurationSeconds) && targetDurationSeconds > 0
    ? targetDurationSeconds
    : currentPlan === "pro"
      ? 3600
      : 1800;
  const estimatedFrontTaskSeconds = hasBackendQueueEta ? 0 : (queuedAheadCount + activeTaskAheadCount) * estimatedSingleTaskSeconds;
  const baseRemainingSeconds = Number.isFinite(remainingSeconds) ? Math.max(0, remainingSeconds) : 0;
  const displayRemainingSeconds = hasBackendQueueEta ? Math.max(0, backendQueueEtaSeconds) : baseRemainingSeconds + estimatedFrontTaskSeconds;
  const displayEstimatedCompletedAt = estimatedCompletedAt
    ? formatApproxTimeWithOffset(estimatedCompletedAt, estimatedFrontTaskSeconds)
    : displayRemainingSeconds > 0
      ? formatApproxTimeAfterSeconds(displayRemainingSeconds)
      : "";
  const durationTracking = ["running", "queued", "submitted", "retrying", "report_waiting"].includes(currentStatus) && displayRemainingSeconds > 0;
  const presentationStatus = userFacingTaskStatus(currentStatus, task.message, project?.error_reason);
  const visibleTaskMessage = userFacingTaskMessage(currentStatus, task.message, project?.error_reason);
  const visibleStages = stages.filter((stage) => !hiddenBusinessLogStages.has(textValue(stage.key || stage.stage).toLowerCase()));
  const visibleLogs = logs.filter(isBusinessLogVisible);
  const showDiagnostics = diagnosticsVisible();
  const taskStartedAt = textValue(project?.started_at || logs.find((item) => textValue(item.stage) === "start")?.timestamp);
  const cancelRequested = currentStatus === "cancel_requested";
  const canCancelTask = Boolean(project?.task_id) && ["submitted", "running", "report_waiting"].includes(normalizedStatus(project?.status)) && !cancelRequested;
  const evidenceLow = lowEvidenceSignal(task, logs);

  if (!projectId) return <Navigate to="/projects" replace />;

  return (
    <AppShell
      user={user}
      onLogout={onLogout}
      onUserChange={onUserChange}
      activeStep={3}
      sidebar={
        <ProjectSidebar
          project={project}
          assistantPage="step3"
          assistantContext={{
            task: {
              status: presentationStatus,
              stage: businessStageLabel(task.stage || task.current_stage),
              percent,
              remaining_seconds: displayRemainingSeconds,
              estimated_completed_at: displayEstimatedCompletedAt
            },
            current_status: presentationStatus,
            progress_percent: percent
          }}
          extra={
            <Card title="控制面板" className="info-card">
              <Space direction="vertical" className="w-full">
                <Button type="primary" icon={<PlayCircleOutlined />} onClick={submitAndRun} loading={runningAction === "run"} block>
                  提交并运行
                </Button>
                <Button danger icon={<StopOutlined />} onClick={cancelTask} loading={runningAction === "cancel"} disabled={!canCancelTask} block>
                  {cancelRequested ? "正在取消" : "取消任务"}
                </Button>
                <Button icon={<ReloadOutlined />} onClick={refreshProgress} block>
                  刷新进度
                </Button>
                <Button type="link" onClick={() => navigate(projectPath(4, projectId))}>
                  查看报告
                </Button>
              </Space>
            </Card>
          }
        />
      }
    >
      <Card className="info-card run-action-card">
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={15}>
            <Space direction="vertical" size={6}>
              <Space wrap>
                <Tag color={statusColor(presentationStatus)}>{statusLabel(presentationStatus)}</Tag>
                <Text strong>{textValue(project?.project_name || "当前仿真项目")}</Text>
              </Space>
              <Text type="secondary">
                配置确认后点击右侧按钮提交，系统会自动完成资料检索、用户模拟、结果汇总和报告生成。
              </Text>
            </Space>
          </Col>
          <Col xs={24} md={9}>
            <Space className="run-action-buttons" wrap>
              {currentStatus === "completed" ? (
                <Button type="primary" size="large" icon={<FileTextOutlined />} onClick={() => navigate(projectPath(4, projectId))}>
                  查看完整报告
                </Button>
              ) : (
                <Button type="primary" size="large" icon={<PlayCircleOutlined />} onClick={submitAndRun} loading={runningAction === "run"}>
                  提交并运行仿真
                </Button>
              )}
              {(canCancelTask || cancelRequested) && (
                <Button
                  danger
                  size="large"
                  icon={<StopOutlined />}
                  onClick={cancelTask}
                  loading={runningAction === "cancel"}
                  disabled={cancelRequested}
                >
                  {cancelRequested ? "正在取消" : "取消任务"}
                </Button>
              )}
              <Button size="large" icon={<ReloadOutlined />} onClick={refreshProgress}>
                刷新进度
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card className="info-card" title="运行进度">
            <Space direction="vertical" size={18} className="w-full">
              <div className="progress-header">
                <Badge status={statusColor(presentationStatus) as "success" | "processing" | "default" | "error" | "warning"} />
                <Tag color={statusColor(presentationStatus)}>
                  {statusLabel(presentationStatus)}
                </Tag>
                <Text type="secondary">{visibleTaskMessage || "等待操作"}</Text>
              </div>
              {durationTracking && (
                <Alert
                  type="info"
                  showIcon
                  message={reportWaiting ? "报告正在生成" : currentStatus === "queued" ? "任务已提交，等待处理" : "仿真正在进行"}
                  description={
                    <Space direction="vertical" size={2}>
                      {taskStartedAt && <Text>任务开始时间：{formatTime(taskStartedAt)}</Text>}
                      {displayEstimatedCompletedAt && <Text>预计完成时间：{displayEstimatedCompletedAt}</Text>}
                      {displayRemainingSeconds > 0 && <Text>当前预计剩余：{formatDurationSeconds(displayRemainingSeconds)}</Text>}
                      {estimatedFrontTaskSeconds > 0 && <Text type="secondary">前序任务预计耗时已计入当前剩余时间。</Text>}
                      {Number.isFinite(targetDurationSeconds) && <Text type="secondary">本次目标生成时长：{formatDurationSeconds(targetDurationSeconds)}</Text>}
                      <Text type="secondary">时间为系统估算值：根据历史测试记录和当前运行情况测算，实际可能受网络、证据检索和模型响应速度影响略有延长。</Text>
                    </Space>
                  }
                />
              )}
              {evidenceLow && (
                <Alert
                  type="warning"
                  showIcon
                  message="资料覆盖较少提示"
                  description="当前公开资料或平台证据库覆盖较少，部分报告图表可能以说明形式展示，不会阻断报告生成。竞品数据不符合您的需要？请联系客服 18960333566。"
                />
              )}
              {currentStatus === "completed" && (
                <Alert
                  type="success"
                  showIcon
                  message="仿真已完成"
                  description={<Button type="primary" icon={<FileTextOutlined />} onClick={() => navigate(projectPath(4, projectId))}>进入 Step4 查看报告</Button>}
                />
              )}
              <Progress percent={percent} strokeColor="#2563eb" />
              <Timeline
                items={(visibleStages.length ? visibleStages : []).map((stage) => ({
                  color: stage.status === "done" ? "green" : stage.status === "current" || stage.status === "failed" ? "blue" : "gray",
                  children: (
                    <Space direction="vertical" size={0}>
                      <Text strong={stage.status === "current"}>{businessStageLabel(stage.key || stage.label)}</Text>
                      <Text type="secondary">{businessStageStatus(stage.status)}</Text>
                    </Space>
                  )
                }))}
              />
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card className="info-card" title="运行状态摘要">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="当前状态">{statusLabel(presentationStatus)}</Descriptions.Item>
              <Descriptions.Item label="当前阶段">{businessStageLabel(task.stage || task.current_stage || "-")}</Descriptions.Item>
              <Descriptions.Item label="预计完成">{displayEstimatedCompletedAt || "-"}</Descriptions.Item>
              <Descriptions.Item label="当前预计剩余">{displayRemainingSeconds > 0 ? formatDurationSeconds(displayRemainingSeconds) : "-"}</Descriptions.Item>
              <Descriptions.Item label="状态提示">{visibleTaskMessage || "系统正在按当前配置处理任务"}</Descriptions.Item>
            </Descriptions>
            {showDiagnostics && <details className="technical-diagnostics">
              <summary>技术诊断</summary>
              <Descriptions column={1} size="small" className="mt-12">
                <Descriptions.Item label="总排队数">{totalQueueLength()}</Descriptions.Item>
                <Descriptions.Item label="普通版队列">{Number(((queueStatus.lengths as JsonObject | undefined)?.basic) || 0)}</Descriptions.Item>
                <Descriptions.Item label="专业版队列">{Number(((queueStatus.lengths as JsonObject | undefined)?.pro) || 0)}</Descriptions.Item>
                <Descriptions.Item label="Worker 心跳">{workerHeartbeatCount}</Descriptions.Item>
                <Descriptions.Item label="任务心跳">{taskHeartbeatCount}</Descriptions.Item>
                <Descriptions.Item label="等待诊断">{textValue(queueDiagnostics.message || "-")}</Descriptions.Item>
                <Descriptions.Item label="运行锁">{Number(queueStatus.project_lock_count || 0)}</Descriptions.Item>
              </Descriptions>
            </details>}
          </Card>
          <Card className="info-card" title="配置摘要">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="产品">{textValue(project?.product_definition?.product_name || project?.product_definition?.name)}</Descriptions.Item>
              <Descriptions.Item label="品牌">{textValue(project?.product_definition?.brand || "-")}</Descriptions.Item>
              <Descriptions.Item label="价格">{textValue(project?.product_definition?.price_cny || "-")}</Descriptions.Item>
              <Descriptions.Item label="人群">{marketCrowdSummary(project?.market_config)}</Descriptions.Item>
              <Descriptions.Item label="策略">{marketStrategySummary(project?.market_config)}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col span={24}>
          <Card className="info-card" title="运行日志">
            {visibleLogs.length ? (
              <Timeline
                items={visibleLogs.map((item) => ({
                  color: textValue(item.stage) === "completed" ? "green" : "blue",
                  children: (
                    <div>
                      <Text strong>{businessStageLabel(item.stage)}</Text>
                      <Text type="secondary"> · {formatDate(item.timestamp)}</Text>
                      <div>{businessLogMessage(item)}</div>
                    </div>
                  )
                }))}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可展示的业务日志；任务启动后会自动更新" />
            )}
          </Card>
        </Col>
      </Row>
    </AppShell>
  );
}

function MetricCards({ report }: { report: JsonObject }) {
  const chart = getChartData(report);
  const overview = (chart.overview_metrics || {}) as JsonObject;
  const aggregation = (report.aggregation || report.metrics || {}) as JsonObject;
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} sm={12} lg={6}>
        <Card className="metric-card">
          <Statistic title="购买意愿指数" value={Number(overview.purchase_intent_index ?? Number(aggregation.purchase_intent_avg ?? 0) * 100)} precision={1} suffix="%" />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card className="metric-card">
          <Statistic title="预估市场份额" value={Number(overview.estimated_market_share ?? 0)} precision={1} suffix="%" />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card className="metric-card">
          <Statistic title="目标匹配度" value={textValue(overview.target_match || "-")} />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card className="metric-card">
          <Statistic title="证据 / 竞品" value={`${Number(overview.evidence_count ?? 0)} / ${Number(overview.competitor_count ?? 0)}`} />
        </Card>
      </Col>
    </Row>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="nested-card" title={title}>
      {children}
    </Card>
  );
}

function PurchaseIntentChart({ report }: { report: JsonObject }) {
  const rows = chartRows(getChartData(report).purchase_intent_by_segment);
  if (!rows.length) return <ChartMissingNotice kind="crowd" />;
  const option = {
    ...chartBase(),
    tooltip: { ...(chartBase().tooltip as JsonObject), trigger: "axis", formatter: chartTooltipFormatter("%") },
    grid: { left: 42, right: 20, top: 26, bottom: rows.length > 4 ? 70 : 48, containLabel: true },
    xAxis: chartAxis({
      type: "category",
      data: rows.map((item) => chartName(item.name, 10)),
      axisLabel: chartAxisLabel({ rotate: rows.length > 4 ? 28 : 0, width: 78 })
    }),
    yAxis: chartAxis({ type: "value", min: 0, max: 100 }),
    series: [
      {
        type: "bar",
        name: "购买意愿",
        data: rows.map((item) => ({ value: Number(item.value ?? 0), fullName: textValue(item.name) })),
        barWidth: 22,
        itemStyle: { borderRadius: [6, 6, 0, 0] }
      }
    ]
  };
  return <ReactECharts className="chart" option={option} notMerge lazyUpdate />;
}

function MarketShareChart({ report }: { report: JsonObject }) {
  const rows = chartRows(getChartData(report).market_share);
  if (!rows.length) return <ChartMissingNotice kind="market" />;
  const option = {
    ...chartBase(),
    tooltip: {
      ...(chartBase().tooltip as JsonObject),
      trigger: "item",
      formatter: (params: unknown) => {
        const row = params as JsonObject;
        const data = (row.data || {}) as JsonObject;
        const name = textValue(data.fullName || row.name);
        return `${name}<br/>占比：${Number(row.percent ?? data.value ?? 0).toFixed(1)}%`;
      }
    },
    legend: {
      type: "scroll",
      bottom: 0,
      height: 52,
      pageIconColor: CHART_PALETTE[0],
      pageTextStyle: { color: CHART_TEXT_COLOR },
      textStyle: { color: CHART_TEXT_COLOR, width: 130, overflow: "truncate" }
    },
    series: [
      {
        type: "pie",
        radius: ["36%", "55%"],
        center: ["43%", "39%"],
        avoidLabelOverlap: true,
        minShowLabelAngle: 5,
        data: rows.map((item) => ({ name: chartName(item.name, 10), fullName: textValue(item.name), value: Number(item.share ?? item.value ?? 0) })),
        label: { color: CHART_TEXT_COLOR, alignTo: "edge", edgeDistance: 8, formatter: "{b}\n{d}%", width: 86, overflow: "truncate" },
        labelLine: { length: 8, length2: 10, maxSurfaceAngle: 80 },
        labelLayout: { hideOverlap: true, moveOverlap: "shiftY" }
      }
    ]
  };
  return <ReactECharts className="chart" option={option} notMerge lazyUpdate />;
}

function ParamImportanceChart({ report }: { report: JsonObject }) {
  const rows = chartRows(getChartData(report).param_importance);
  if (!rows.length) return <ChartMissingNotice kind="params" />;
  const option = {
    ...chartBase(),
    tooltip: { ...(chartBase().tooltip as JsonObject), trigger: "axis", formatter: chartTooltipFormatter("%") },
    grid: { left: 104, right: 18, top: 24, bottom: 40, containLabel: true },
    xAxis: chartAxis({ type: "value", min: 0, max: 100 }),
    yAxis: chartAxis({ type: "category", data: rows.map((item) => chartName(item.name, 12)).reverse(), axisLabel: chartAxisLabel({ width: 92 }) }),
    series: [
      {
        type: "bar",
        name: "重要性",
        data: rows.map((item) => ({ value: Number(item.importance ?? 0), fullName: textValue(item.name) })).reverse(),
        barWidth: 18,
        itemStyle: { borderRadius: [0, 6, 6, 0] }
      }
    ]
  };
  return <ReactECharts className="chart" option={option} notMerge lazyUpdate />;
}

function PriceSensitivityChart({ report }: { report: JsonObject }) {
  const rows = chartRows(getChartData(report).price_sensitivity);
  if (!rows.length) return <ChartMissingNotice kind="price" />;
  const option = {
    ...chartBase(),
    tooltip: { ...(chartBase().tooltip as JsonObject), trigger: "axis", formatter: chartTooltipFormatter("%") },
    grid: { left: 48, right: 22, top: 24, bottom: 62, containLabel: true },
    xAxis: chartAxis({ type: "category", data: rows.map((item) => `￥${item.price}`), axisLabel: chartAxisLabel({ rotate: rows.length > 5 ? 28 : 0, width: 80 }) }),
    yAxis: chartAxis({ type: "value", min: 0, max: 100 }),
    series: [
      {
        type: "line",
        smooth: true,
        name: "购买意愿",
        data: rows.map((item) => ({ value: Number(item.intent ?? 0), fullName: `价格 ￥${item.price}` })),
        symbol: "circle",
        symbolSize: 7,
        lineStyle: { width: 3, color: CHART_PALETTE[0] },
        areaStyle: { color: "rgba(202, 224, 244, 0.42)" }
      }
    ]
  };
  return <ReactECharts className="chart" option={option} notMerge lazyUpdate />;
}

function StrategyRoiChart({ report }: { report: JsonObject }) {
  const rows = chartRows(getChartData(report).strategy_roi).length
    ? chartRows(getChartData(report).strategy_roi)
    : chartRows(report.strategy_roi);
  if (!rows.length) return <ChartMissingNotice kind="strategy" />;
  const option = {
    ...chartBase(),
    tooltip: { ...(chartBase().tooltip as JsonObject), trigger: "axis", formatter: chartTooltipFormatter("") },
    grid: { left: 48, right: 22, top: 24, bottom: 76, containLabel: true },
    xAxis: chartAxis({ type: "category", data: rows.map((item) => chartName(item.name, 10)), axisLabel: chartAxisLabel({ rotate: rows.length > 3 ? 32 : 0, width: 86 }) }),
    yAxis: chartAxis({ type: "value" }),
    series: [
      {
        type: "bar",
        name: "ROI",
        data: rows.map((item) => ({ value: Number(item.roi ?? 0), fullName: textValue(item.name) })),
        barWidth: 24,
        itemStyle: { borderRadius: [6, 6, 0, 0] }
      }
    ]
  };
  return <ReactECharts className="chart" option={option} notMerge lazyUpdate />;
}

function ChannelEffectChart({ report }: { report: JsonObject }) {
  const rows = chartRows(getChartData(report).channel_effect).length
    ? chartRows(getChartData(report).channel_effect)
    : chartRows(report.channel_effect);
  if (!rows.length) return <ChartMissingNotice kind="strategy" />;
  const option = {
    ...chartBase(),
    tooltip: { ...(chartBase().tooltip as JsonObject), trigger: "axis", formatter: chartTooltipFormatter("%") },
    grid: { left: 48, right: 22, top: 24, bottom: 76, containLabel: true },
    xAxis: chartAxis({ type: "category", data: rows.map((item) => chartName(item.name || item.channel, 10)), axisLabel: chartAxisLabel({ rotate: rows.length > 3 ? 32 : 0, width: 86 }) }),
    yAxis: chartAxis({ type: "value", min: 0, max: 100 }),
    series: [
      {
        type: "bar",
        name: "渠道贡献",
        data: rows.map((item) => ({ value: Number(item.effect ?? item.value ?? 0), fullName: textValue(item.name || item.channel) })),
        barWidth: 24,
        itemStyle: { borderRadius: [6, 6, 0, 0] }
      }
    ]
  };
  return <ReactECharts className="chart" option={option} notMerge lazyUpdate />;
}

function SocialEvolutionChart({ report }: { report: JsonObject }) {
  const rows = chartRows(getChartData(report).social_evolution);
  if (!rows.length) return <ChartMissingNotice kind="social" />;
  const rounds = Array.from(new Set(rows.map((item) => Number(item.round || 0)))).filter(Boolean).sort((a, b) => a - b);
  const names = Array.from(new Set(rows.map((item) => textValue(item.name || "整体人群"))));
  const option = {
    ...chartBase(),
    tooltip: { ...(chartBase().tooltip as JsonObject), trigger: "axis" },
    legend: { type: "scroll", bottom: 0, height: 54, textStyle: { color: CHART_TEXT_COLOR, width: 120, overflow: "truncate" } },
    grid: { left: 48, right: 24, top: 28, bottom: 70, containLabel: true },
    xAxis: chartAxis({ type: "category", data: rounds.map((round) => `第 ${round} 轮`) }),
    yAxis: chartAxis({ type: "value", min: 0, max: 100 }),
    series: names.map((name) => ({
      type: "line",
      smooth: true,
      name,
      data: rounds.map((round) => {
        const row = rows.find((item) => Number(item.round) === round && textValue(item.name || "整体人群") === name);
        return row ? Number(row.value ?? 0) : null;
      }),
      symbol: "circle",
      symbolSize: 7,
      lineStyle: { width: name === "整体人群" ? 4 : 2 }
    }))
  };
  return <ReactECharts className="chart" option={option} notMerge lazyUpdate />;
}

function SensitivityWaterfallChart({ report }: { report: JsonObject }) {
  const rows = chartRows(getChartData(report).sensitivity_waterfall);
  if (!rows.length) return <ChartMissingNotice kind="sensitivity" />;
  const option = {
    ...chartBase(),
    tooltip: { ...(chartBase().tooltip as JsonObject), trigger: "axis", formatter: chartTooltipFormatter("") },
    grid: { left: 48, right: 22, top: 24, bottom: 76, containLabel: true },
    xAxis: chartAxis({ type: "category", data: rows.map((item) => chartName(item.name || item.parameter, 10)), axisLabel: chartAxisLabel({ rotate: rows.length > 3 ? 32 : 0, width: 86 }) }),
    yAxis: chartAxis({ type: "value" }),
    series: [
      {
        type: "bar",
        name: "影响幅度",
        data: rows.map((item) => ({ value: Number(item.impact ?? item.value ?? 0), fullName: textValue(item.name || item.parameter) })),
        barWidth: 24,
        itemStyle: { borderRadius: [6, 6, 0, 0] }
      }
    ]
  };
  return <ReactECharts className="chart" option={option} notMerge lazyUpdate />;
}

function CompetitorRadarChart({ report }: { report: JsonObject }) {
  const radar = getChartData(report).competitor_radar as JsonObject | undefined;
  const dimensions = Array.isArray(radar?.dimensions) ? (radar.dimensions as unknown[]) : [];
  const series = Array.isArray(radar?.series) ? (radar.series as JsonObject[]) : [];
  if (!dimensions.length || !series.length) return <ChartMissingNotice kind="competitor" />;
  const option = {
    ...chartBase(),
    tooltip: {
      ...(chartBase().tooltip as JsonObject),
      formatter: (params: unknown) => {
        const row = params as JsonObject;
        const data = (row.data || {}) as JsonObject;
        return `${textValue(data.fullName || row.name)}<br/>${(Array.isArray(data.value) ? data.value : []).join(" / ")}`;
      }
    },
    legend: { type: "scroll", bottom: 0, height: 56, textStyle: { color: CHART_TEXT_COLOR, width: 130, overflow: "truncate" } },
    radar: {
      indicator: dimensions.map((name) => ({ name: chartName(name, 8), max: 100 })),
      radius: "46%",
      center: ["50%", "39%"],
      axisName: { color: CHART_TEXT_COLOR, width: 72, overflow: "break", lineHeight: 14 },
      splitLine: { lineStyle: { color: CHART_GRID_COLOR } },
      splitArea: { areaStyle: { color: ["rgba(202,224,244,0.18)", "rgba(227,216,230,0.18)"] } },
      axisLine: { lineStyle: { color: CHART_AXIS_COLOR } }
    },
    series: [
      {
        type: "radar",
        data: series.map((item) => ({ name: chartName(item.name, 12), fullName: textValue(item.name), value: Array.isArray(item.values) ? item.values : [] }))
      }
    ]
  };
  return <ReactECharts className="chart" option={option} notMerge lazyUpdate />;
}

function ReportChartGrid({ report, pro }: { report: JsonObject; pro: boolean }) {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={12}>
        <ChartCard title="市场占比">
          <MarketShareChart report={report} />
        </ChartCard>
      </Col>
      <Col xs={24} lg={12}>
        <ChartCard title="购买意愿">
          <PurchaseIntentChart report={report} />
        </ChartCard>
      </Col>
      <Col xs={24} lg={12}>
        <ChartCard title="功能重要性">
          <ParamImportanceChart report={report} />
        </ChartCard>
      </Col>
      <Col xs={24} lg={12}>
        <ChartCard title="价格敏感曲线">
          <PriceSensitivityChart report={report} />
        </ChartCard>
      </Col>
      {pro && (
        <>
          <Col xs={24} lg={12}>
            <ChartCard title="策略 ROI">
              <StrategyRoiChart report={report} />
            </ChartCard>
          </Col>
          <Col xs={24} lg={12}>
            <ChartCard title="竞品五维雷达">
              <CompetitorRadarChart report={report} />
            </ChartCard>
          </Col>
        </>
      )}
    </Row>
  );
}

function MautAnalysis({ report }: { report: JsonObject }) {
  const decisionModel = (report.decision_model || {}) as JsonObject;
  const aggregation = (report.aggregation || {}) as JsonObject;
  const dimensionScores = ((aggregation.dimension_scores || decisionModel.dimension_scores || {}) as JsonObject) || {};
  const confidence = ((aggregation.confidence || decisionModel.confidence || {}) as JsonObject) || {};
  const weightRows = Array.isArray(decisionModel.weights) ? (decisionModel.weights as JsonObject[]) : [];
  const dimensionRows: JsonObject[] = Object.entries(dimensionScores).map(([key, value]) => ({
    key,
    ...((value as JsonObject) || {})
  }));
  const confidenceColor = confidence.color === "green" ? "success" : confidence.color === "red" ? "error" : "warning";
  const confidenceComponents = ((confidence.components || {}) as JsonObject) || {};
  const confidenceComponentOrder = [
    "logic_format_score",
    "competitor_price_coverage_score",
    "rag_evidence_score",
    "crowd_profile_completeness_score"
  ];
  const confidenceRows: JsonObject[] = confidenceComponentOrder
    .map((key) => {
      const value = confidenceComponents[key] as JsonObject | undefined;
      return value ? { key, ...value } : null;
    })
    .filter(Boolean) as JsonObject[];
  const topDimension = [...dimensionRows].sort((a, b) => Number(b.weighted_contribution || 0) - Number(a.weighted_contribution || 0))[0];
  const modelIncomplete = !dimensionRows.length || !weightRows.length;
  return (
    <Space direction="vertical" size={16} className="w-full">
      {modelIncomplete && <ChartMissingNotice kind="model" />}
      <Card className="nested-card" title="购买意愿计算说明">
        <Paragraph>
          平台将每个虚拟消费者的购买意愿拆成五个业务维度：功能是否匹配、价格是否可接受、促销是否有拉动、品牌是否值得信任、以及社交影响是否正向。
          当前样本中贡献最高的是 <Text strong>{textValue(topDimension?.label || "功能匹配度")}</Text>，
          加权贡献约为 <Text strong>{scorePct(topDimension?.weighted_contribution)}</Text>。
        </Paragraph>
        <div className="formula-block" aria-label="购买意愿公式">
          <span className="formula-name">购买意愿</span>
          <span>=</span>
          <span>100 × clip(0.30 × S<sub>f</sub> + 0.25 × S<sub>p</sub> + 0.10 × B<sub>pr</sub> + 0.15 × B<sub>b</sub> + 0.20 × S<sub>s</sub>)</span>
        </div>
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card className="metric-card">
            <Statistic title="证据置信度" value={Number(confidence.score ?? 0) * 100} precision={1} suffix="%" />
            <Tag className="mt-16" color={confidenceColor}>{textValue(confidence.label || "-")}置信度</Tag>
          </Card>
        </Col>
        <Col xs={24} md={16}>
          <Card className="nested-card" title="证据置信度说明">
            <Paragraph>
              证据置信度由逻辑/格式、竞品价格覆盖率、RAG 证据数量/质量和用户画像完整度四项加权得到。
              当前等级为 <Text strong>{textValue(confidence.label || "-")}</Text>，用于判断本轮报告依据是否充分，不代表市场预测一定准确。
            </Paragraph>
            <div className="formula-block compact" aria-label="证据置信度公式">
              <span className="formula-name">证据置信度</span>
              <span>=</span>
              <span>0.40 × C<sub>logic</sub> + 0.25 × C<sub>price</sub> + 0.20 × C<sub>rag</sub> + 0.15 × C<sub>profile</sub></span>
            </div>
            {confidenceRows.length > 0 && (
              <Table
                className="mb-16"
                size="small"
                pagination={false}
                rowKey="key"
                dataSource={confidenceRows}
                columns={[
                  { title: "分项", dataIndex: "label" },
                  { title: "得分", dataIndex: "score", render: (value) => `${(Number(value || 0) * 100).toFixed(1)}%` },
                  { title: "权重", dataIndex: "weight", render: (value) => `${(Number(value || 0) * 100).toFixed(0)}%` }
                ]}
              />
            )}
            <List
              size="small"
              dataSource={Array.isArray(confidence.manual_review_suggestions) ? confidence.manual_review_suggestions as string[] : ["当前结论可作为演示分析使用，正式上线前建议补充更多真实市场语料。"]}
              renderItem={(item) => <List.Item>{item}</List.Item>}
            />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card className="nested-card" title="五维权重">
            <Table
              size="small"
              pagination={false}
              rowKey={(record) => String(record.dimension || record.label)}
              dataSource={weightRows}
              columns={[
                { title: "维度", dataIndex: "label" },
                { title: "符号", dataIndex: "symbol" },
                { title: "权重", dataIndex: "weight", render: (value) => Number(value).toFixed(2) }
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card className="nested-card" title="五维均值">
            <Table
              size="small"
              pagination={false}
              rowKey="key"
              dataSource={dimensionRows}
              columns={[
                { title: "维度", dataIndex: "label" },
                { title: "均值", dataIndex: "avg_score", render: (value) => `${(Number(value || 0) * 100).toFixed(1)}%` },
                { title: "贡献", dataIndex: "weighted_contribution", render: (value) => `${(Number(value || 0) * 100).toFixed(1)}%` }
              ]}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}

function SocialPropagationAnalysis({ report, pro }: { report: JsonObject; pro: boolean }) {
  const social = (report.social_simulation || {}) as JsonObject;
  const rounds = chartRows(social.round_summaries);
  if (!rounds.length) {
    return <ChartMissingNotice kind="social" />;
  }
  const converged = Boolean(social.converged);
  return (
    <Space direction="vertical" size={16} className="w-full">
      <Alert
        type={converged ? "success" : "info"}
        showIcon
        message={converged ? "社交传播已提前收敛" : "社交传播已完成"}
        description={`系统在小世界关系网络中执行了 ${Number(social.rounds_executed || rounds.length)} 轮传播，购买意愿会随着邻居反馈逐轮调整。`}
      />
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}><Card className="metric-card"><Statistic title="代表用户" value={Number(social.node_count || 0)} /></Card></Col>
        <Col xs={12} md={6}><Card className="metric-card"><Statistic title="关系边" value={Number(social.edge_count || 0)} /></Card></Col>
        <Col xs={12} md={6}><Card className="metric-card"><Statistic title="平均连接数" value={Number(social.average_degree || 0)} precision={1} /></Card></Col>
        <Col xs={12} md={6}><Card className="metric-card"><Statistic title="传播轮数" value={Number(social.rounds_executed || rounds.length)} /></Card></Col>
      </Row>
      <ChartCard title={pro ? "整体与分客群购买意愿演化" : "整体购买意愿演化"}>
        <SocialEvolutionChart report={report} />
      </ChartCard>
      {pro && (
        <Card className="nested-card" title="传播轮次摘要">
          <Table
            size="small"
            pagination={false}
            rowKey={(record) => String(record.round)}
            dataSource={rounds}
            columns={[
              { title: "轮次", dataIndex: "round", render: (value) => `第 ${value} 轮` },
              { title: "整体购买意愿", dataIndex: "overall_purchase_intent", render: (value) => `${(Number(value || 0) * 100).toFixed(1)}%` },
              { title: "社会影响均值", dataIndex: "social_influence_avg", render: (value) => `${(Number(value || 0) * 100).toFixed(1)}%` },
              { title: "最大变化", dataIndex: "max_score_change", render: (value) => `${(Number(value || 0) * 100).toFixed(1)}%` },
              {
                title: "辅助模型",
                dataIndex: "validation",
                render: (value) => {
                  const validation = (value || {}) as JsonObject;
                  return validation.enabled ? textValue(validation.status || "已复核") : "未启用";
                }
              }
            ]}
          />
        </Card>
      )}
    </Space>
  );
}

function ReportNarrative({ report }: { report: JsonObject }) {
  const chart = getChartData(report);
  const overview = (chart.overview_metrics || {}) as JsonObject;
  const aggregation = (report.aggregation || {}) as JsonObject;
  const dimensionScores = ((aggregation.dimension_scores || {}) as JsonObject) || {};
  const rows: JsonObject[] = Object.entries(dimensionScores).map(([key, value]) => ({ key, ...((value as JsonObject) || {}) }));
  const top = [...rows].sort((a, b) => Number(b.weighted_contribution || 0) - Number(a.weighted_contribution || 0))[0];
  const weak = [...rows].sort((a, b) => Number(a.weighted_contribution || 0) - Number(b.weighted_contribution || 0))[0];
  const confidence = ((aggregation.confidence || {}) as JsonObject) || {};
  const priceCoverage = ((aggregation.evidence_quality || report.data_quality || {}) as JsonObject).price_coverage_pct;
  return (
    <Card className="nested-card" title="报告解读">
      <Space direction="vertical" size={10} className="w-full">
        <Paragraph>
          本轮仿真得到的购买意愿指数为 <Text strong>{pct(overview.purchase_intent_index ?? Number(aggregation.purchase_intent_avg || 0) * 100)}</Text>，
          规则化预估市场份额为 <Text strong>{pct(overview.estimated_market_share)}</Text>。这个份额来自 Agent 购买决策和竞品相对吸引力归一计算，不由大模型直接编造。
        </Paragraph>
        <Paragraph>
          五维拆解中，<Text strong>{textValue(top?.label || "功能匹配度")}</Text> 是当前最强支撑项，
          贡献约 <Text strong>{scorePct(top?.weighted_contribution)}</Text>；
          <Text strong>{textValue(weak?.label || "价格接受度")}</Text> 是相对薄弱项，
          贡献约 <Text strong>{scorePct(weak?.weighted_contribution)}</Text>。这意味着销售表达应优先放大强项，同时补足薄弱项的证据或策略。
        </Paragraph>
        <Paragraph>
          当前证据置信度为 <Text strong>{textValue(confidence.label || "-")}</Text>（{scorePct(confidence.score)}）。
          竞品价格覆盖率为 <Text strong>{Number(priceCoverage ?? 0).toFixed(1)}%</Text>；
          如果价格覆盖率偏低，报告里的价格带和敏感性结论应被视为方向性建议，而不是最终定价依据。
        </Paragraph>
      </Space>
    </Card>
  );
}

function CrowdAnalysis({ report }: { report: JsonObject }) {
  const agents = chartRows(report.agent_samples).slice(0, 12);
  const targetSegments = chartRows(report.target_segments);
  const configuredSegments = chartRows(report.crowd_segments);
  const crowdProfile = (report.crowd_profile || targetSegments[0]?.crowd_profile || {}) as JsonObject;
  const profileSegments: JsonObject[] = configuredSegments.length
    ? configuredSegments
    : targetSegments.length
      ? targetSegments.map((item) => ({ name: item.name || item.segment, ratio: item.ratio || 100, profile: item.crowd_profile || {} } as JsonObject))
      : [{ name: crowdProfile.name || "目标用户", ratio: 100, profile: crowdProfile } as JsonObject];
  const chart = getChartData(report);
  const distribution = chartRows(chart.purchase_intent_distribution);
  const drivers = chartRows(chart.purchase_drivers);
  const blockers = chartRows(chart.purchase_blockers);
  function profileRowsFor(segment: JsonObject) {
    const profile = (segment.profile || segment.crowd_profile || {}) as JsonObject;
    return [
      ["年龄段", profile.age_range],
      ["城市层级", profile.city_tier],
      ["收入水平", profile.income_level],
      ["职业/家庭阶段", profile.life_stage],
      ["价格敏感度", ({ high: "高", medium: "中", low: "低" } as Record<string, string>)[textValue(profile.price_sensitivity)] || profile.price_sensitivity],
      ["功能偏好", Array.isArray(profile.feature_priorities) ? profile.feature_priorities.join("、") : ""],
      ["渠道偏好", Array.isArray(profile.channel_preferences) ? profile.channel_preferences.join("、") : ""],
      ["购买动机", Array.isArray(profile.purchase_motivations) ? profile.purchase_motivations.join("、") : ""],
      ["风险顾虑", Array.isArray(profile.risk_concerns) ? profile.risk_concerns.join("、") : ""]
    ].filter(([, value]) => textValue(value));
  }
  return (
    <Space direction="vertical" size={16} className="w-full">
      <Card className="nested-card" title="目标人群画像">
        <div className="report-crowd-profiles">
          {profileSegments.map((segment, index) => {
            const rows = profileRowsFor(segment);
            const profile = (segment.profile || segment.crowd_profile || {}) as JsonObject;
            return (
              <div className="report-crowd-profile" key={`${textValue(segment.name)}-${index}`}>
                <Space wrap>
                  <Text strong>{textValue(segment.name || profile.name || "目标用户")}</Text>
                  <Tag color="blue">{numberValue(segment.ratio, 100)}%</Tag>
                </Space>
                {rows.length ? (
                  <Descriptions className="mt-16" size="small" column={{ xs: 1, md: 2 }}>
                    {rows.map(([label, value]) => (
                      <Descriptions.Item key={String(label)} label={String(label)}>
                        {textValue(value)}
                      </Descriptions.Item>
                    ))}
                  </Descriptions>
                ) : (
                  <Text type="secondary">暂无结构化画像</Text>
                )}
                {textValue(profile.custom_description) && <Paragraph>{textValue(profile.custom_description)}</Paragraph>}
              </div>
            );
          })}
        </div>
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <ChartCard title="人群购买意愿">
            <PurchaseIntentChart report={report} />
          </ChartCard>
        </Col>
        <Col xs={24} lg={12}>
          <Card className="nested-card" title="目标人群摘要">
            {targetSegments.length ? (
              <List
                dataSource={targetSegments}
                renderItem={(item) => <List.Item>{textValue(item.name || item.segment)}（{numberValue(item.ratio, 100)}%）：{shortText(item.insight || item.summary || item.description)}</List.Item>}
              />
            ) : (
              <ChartMissingNotice kind="crowd" />
            )}
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card className="nested-card" title="购买意愿分布">
            <List
              size="small"
              dataSource={distribution.length ? distribution : [{ name: "暂无分布数据", count: 0 }]}
              renderItem={(item) => (
                <List.Item>
                  <Text>{textValue(item.name)}</Text>
                  <Text strong>{textValue(item.count)}</Text>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card className="nested-card" title="主要购买驱动">
            <List
              size="small"
              dataSource={drivers.length ? drivers.slice(0, 6) : [{ name: "暂无显著驱动因素", count: 0 }]}
              renderItem={(item) => <List.Item>{textValue(item.name)}：{textValue(item.count)} 次提及</List.Item>}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card className="nested-card" title="主要购买阻碍">
            <List
              size="small"
              dataSource={blockers.length ? blockers.slice(0, 6) : [{ name: "暂无显著阻碍因素", count: 0 }]}
              renderItem={(item) => <List.Item>{textValue(item.name)}：{textValue(item.count)} 次提及</List.Item>}
            />
          </Card>
        </Col>
      </Row>
      <Card className="nested-card" title="Agent 样本">
        <Table<JsonObject>
          size="small"
          pagination={{ pageSize: 6 }}
          rowKey={(record) => textValue(record.agent_id || record.id)}
          dataSource={agents}
          columns={[
            { title: "Agent", dataIndex: "agent_id" },
            { title: "人群", dataIndex: "segment" },
            { title: "客群占比", dataIndex: "segment_ratio", render: (value) => `${numberValue(value, 100)}%` },
            { title: "决策风格", dataIndex: "decision_style" },
            { title: "价格敏感", dataIndex: "price_sensitivity" },
            { title: "关注功能", dataIndex: "preferred_features", render: (value: unknown) => Array.isArray(value) ? value.join("、") : textValue(value) }
          ]}
        />
      </Card>
    </Space>
  );
}

function StrategyAnalysis({ report }: { report: JsonObject }) {
  const recommendations = normalizeStrategyRecommendations(report.strategy_recommendations);
  const structuredRecommendations = recommendations.filter((item) => item.structured);
  const plainRecommendations = recommendations.filter((item) => !item.structured);
  const evidence = chartRows(report.market_strategy_evidence);
  const strategyRowsData = chartRows(getChartData(report).strategy_roi).length
    ? chartRows(getChartData(report).strategy_roi)
    : chartRows(report.strategy_roi);
  return (
    <Space direction="vertical" size={16} className="w-full">
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <ChartCard title="策略 ROI">
            <StrategyRoiChart report={report} />
          </ChartCard>
        </Col>
        <Col xs={24} lg={12}>
          <ChartCard title="渠道贡献">
            <ChannelEffectChart report={report} />
          </ChartCard>
        </Col>
      </Row>
      <Card className="nested-card" title="策略建议">
        {structuredRecommendations.length > 0 && (
          <div className="strategy-recommendation-list">
            {structuredRecommendations.map((item, index) => (
              <article className="strategy-recommendation-item" key={`${item.strategy}-${index}`}>
                <Text strong>{item.strategy}</Text>
                {item.actions.length > 0 && (
                  <List
                    size="small"
                    className="strategy-action-list"
                    dataSource={item.actions}
                    renderItem={(action) => <List.Item>{action}</List.Item>}
                  />
                )}
                {item.expectedImpact && <Paragraph className="strategy-impact">预期影响：{item.expectedImpact}</Paragraph>}
              </article>
            ))}
          </div>
        )}
        <List
          size="small"
          dataSource={plainRecommendations.length
            ? plainRecommendations.map((item) => item.strategy)
            : structuredRecommendations.length
              ? []
              : ["建议补充渠道、促销和竞品价格证据后再形成正式投放方案。"]}
          renderItem={(item) => <List.Item>{item}</List.Item>}
        />
      </Card>
      <Card className="nested-card" title="ROI 拆解">
        <Table<JsonObject>
          size="small"
          pagination={false}
          rowKey={(record, index) => `${textValue(record.name || "strategy")}-${index}`}
          dataSource={strategyRowsData}
          columns={[
            { title: "策略", dataIndex: "name" },
            { title: "ROI", dataIndex: "roi", render: (value: unknown) => Number(value || 0).toFixed(2) },
            { title: "触达", dataIndex: "reach_score", render: (value: unknown) => pct(value) },
            { title: "转化拉动", dataIndex: "conversion_lift", render: (value: unknown) => pct(value) },
            { title: "成本压力", dataIndex: "cost_pressure", render: (value: unknown) => pct(value) },
            { title: "风险扣分", dataIndex: "risk_penalty", render: (value: unknown) => pct(value) }
          ]}
        />
      </Card>
      <Card className="nested-card" title="策略证据">
        <EvidenceTable rows={evidence} emptyDescription={chartMissingText("strategy")} />
      </Card>
    </Space>
  );
}

function CompetitorAnalysis({ report, pro }: { report: JsonObject; pro: boolean }) {
  const evidence = chartRows(report.structured_product_evidence || report.evidence_used).filter((item) => textValue(item.source_type).includes("product"));
  return (
    <Space direction="vertical" size={16} className="w-full">
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <ChartCard title="市场占比">
            <MarketShareChart report={report} />
          </ChartCard>
        </Col>
        <Col xs={24} lg={12}>
          <ChartCard title="竞品五维雷达">
            {pro ? <CompetitorRadarChart report={report} /> : <Alert type="info" showIcon icon={<LockOutlined />} message="普通版不展示竞品五维雷达；专业版新项目会生成完整雷达数据。" />}
          </ChartCard>
        </Col>
      </Row>
      <Card className="nested-card" title="竞品证据">
        <EvidenceTable rows={evidence} emptyDescription={chartMissingText("competitor")} />
      </Card>
    </Space>
  );
}

function SensitivityAnalysis({ report, pro }: { report: JsonObject; pro: boolean }) {
  const pricing = (report.pricing_analysis || {}) as JsonObject;
  const chart = getChartData(report);
  const priceBand = (chart.recommended_price_band || {}) as JsonObject;
  const priceRows = chartRows(chart.price_sensitivity);
  return (
    <Space direction="vertical" size={16} className="w-full">
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <ChartCard title="价格敏感曲线">
            <PriceSensitivityChart report={report} />
          </ChartCard>
        </Col>
        <Col xs={24} lg={12}>
          <ChartCard title="参数影响">
            {pro ? <SensitivityWaterfallChart report={report} /> : <ParamImportanceChart report={report} />}
          </ChartCard>
        </Col>
      </Row>
      <Card className="nested-card" title="定价解释">
        <Paragraph>{textValue(pricing.summary || "当前价格敏感性由 Agent 决策和价格变化规则生成，用于判断价格上下浮动对购买意愿的方向性影响。")}</Paragraph>
        <Descriptions size="small" column={{ xs: 1, md: 3 }}>
          <Descriptions.Item label="参考价格">{textValue(pricing.reference_price || "-")}</Descriptions.Item>
          <Descriptions.Item label="价格覆盖率">{pct(((pricing.competitor_price_coverage as JsonObject | undefined)?.price_coverage_pct) || 0)}</Descriptions.Item>
          <Descriptions.Item label="价格缺失竞品">{textValue((pricing.competitor_price_coverage as JsonObject | undefined)?.missing_price_count ?? "-")}</Descriptions.Item>
          <Descriptions.Item label="建议价格带">{textValue(priceBand.min_price ?? "-")} - {textValue(priceBand.max_price ?? "-")}</Descriptions.Item>
          <Descriptions.Item label="峰值意愿">{pct(priceBand.peak_intent)}</Descriptions.Item>
        </Descriptions>
        <Paragraph className="mt-16">{textValue(priceBand.analysis || "建议价格带由价格敏感曲线筛选得到，用于辅助方案讨论。")}</Paragraph>
      </Card>
      <Card className="nested-card" title="价格敏感性明细">
        <Table<JsonObject>
          size="small"
          pagination={false}
          rowKey={(record) => textValue(record.multiplier || record.price)}
          dataSource={priceRows}
          columns={[
            { title: "价格倍率", dataIndex: "multiplier", render: (value: unknown) => `${Number(value || 0).toFixed(2)}x` },
            { title: "价格", dataIndex: "price" },
            { title: "购买意愿", dataIndex: "intent", render: (value: unknown) => pct(value) },
            { title: "弹性系数", dataIndex: "elasticity" },
            { title: "说明", dataIndex: "note" }
          ]}
        />
      </Card>
    </Space>
  );
}

function EvidenceTable({ rows, emptyDescription = "暂无证据" }: { rows: JsonObject[]; emptyDescription?: string }) {
  const data = rows.slice(0, 20);
  if (!data.length && emptyDescription.startsWith("当前报告缺少")) {
    return <Alert className="chart-empty-note" type="info" showIcon message="证据暂未生成" description={emptyDescription} />;
  }
  if (!data.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyDescription} />;
  return (
    <Table<JsonObject>
      size="small"
      pagination={{ pageSize: 6 }}
      rowKey={(record, index) => `${textValue(record.source || record.group || "evidence")}-${index}`}
      dataSource={data}
      columns={[
        { title: "来源", dataIndex: "source", width: 140 },
        { title: "类型", dataIndex: "source_type", width: 150 },
        { title: "分数", dataIndex: "score", width: 90, render: (value: unknown) => Number(value || 0).toFixed(2) },
        { title: "片段", dataIndex: "snippet", render: (value: unknown, record: JsonObject) => shortText(value || record.insight || record.text, 180) }
      ]}
    />
  );
}

function EvidenceAnalysis({ report }: { report: JsonObject }) {
  const rows = flattenEvidence(report);
  const ragCount = ragFinalUsedCount(report);
  const ragMissing = ragCount === 0;
  const qualityWarnings = Array.isArray(report.quality_warnings) ? report.quality_warnings.map(textValue).filter(Boolean) : [];
  const priceQuality = ((report.aggregation as JsonObject | undefined)?.evidence_quality || report.data_quality || {}) as JsonObject;
  const priceCoverage = priceQuality.price_coverage_pct;
  const hasPriceCoverageNote = qualityWarnings.some((item) => /价格|竞品/.test(item)) || Number(priceCoverage ?? 100) < 80;
  return (
    <Space direction="vertical" size={16} className="w-full">
      <Alert
        type="info"
        showIcon
        message="证据说明"
        description="报告只展示脱敏后的证据来源、命中片段和匹配分数；不会显示 API key、prompt 原文或内部日志路径。"
      />
      {hasPriceCoverageNote && (
        <Alert
          type="info"
          showIcon={false}
          className="rag-evidence-note"
          message="证据小结"
          description={
            <Text type="secondary">
              本次竞品数据里有部分价格缺失，价格带和敏感性相关结论建议作为方向参考
              {priceCoverage !== undefined && priceCoverage !== null ? `，当前价格覆盖率约 ${Number(priceCoverage).toFixed(1)}%` : ""}。
              （竞品数据不符合您的需要？请联系客服18960333566.）
            </Text>
          }
        />
      )}
      {ragMissing && (
        <Alert
          type="warning"
          showIcon
          message="证据覆盖较少"
          description={evidenceContactText}
        />
      )}
      <Card className="nested-card" title="证据列表">
        <EvidenceTable
          rows={rows}
          emptyDescription={chartMissingText("rag")}
        />
      </Card>
    </Space>
  );
}

function parseDetailJson(value: unknown): JsonObject {
  if (!value) return {};
  if (typeof value === "object") return value as JsonObject;
  if (typeof value !== "string") return {};
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? (parsed as JsonObject) : {};
  } catch {
    return {};
  }
}

function lowEvidenceSignal(task: JsonObject, logs: JsonObject[]): boolean {
  const candidates = [
    task.evidence_count,
    task.rag_evidence_count,
    task.final_evidence_count,
    (task.rag_summary as JsonObject | undefined)?.total_final_used,
    (task.report_summary as JsonObject | undefined)?.evidence_count
  ];
  for (const value of candidates) {
    const count = Number(value);
    if (Number.isFinite(count)) return count <= 0;
  }
  return logs.some((item) => {
    const stage = textValue(item.stage).toLowerCase();
    const detail = parseDetailJson(item.detail_json);
    const detailCount = Number(detail.total_final_used ?? detail.evidence_count ?? detail.final_used_count);
    if (Number.isFinite(detailCount)) return detailCount <= 0;
    const content = `${textValue(item.message)} ${JSON.stringify(detail)}`;
    return stage.includes("rag") && /(证据|资料|竞品).*(较少|不足|缺少|未检索|为空|没有)/.test(content);
  });
}

function JsonPreview({ data }: { data: unknown }) {
  return <pre className="json-preview">{JSON.stringify(data || {}, null, 2)}</pre>;
}

function Step4Report({ user, onLogout, onUserChange }: { user: User; onLogout: () => void; onUserChange: (user: User) => void }) {
  const projectId = useProjectId();
  const { project, setProject, refreshProject } = useProject(projectId);
  const [shareUrl, setShareUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<"json" | "markdown" | "excel" | "pdf" | "">("");
  const report = unwrapReport(project);
  const pro = isProjectPro(project, user, report);

  async function loadReport() {
    if (!projectId) return;
    setLoading(true);
    try {
      const response = (await api.report(projectId)) as JsonObject;
      setProject((current) => current ? { ...current, status: String(response.status || "completed"), result_data: response.report as JsonObject } : current);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "报告尚未生成");
      await refreshProject();
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadReport();
  }, [projectId]);

  async function waitForExportTask(exportTaskId: string | number): Promise<JsonObject> {
    for (let attempt = 0; attempt < 900; attempt += 1) {
      const status = (await api.exportStatus(exportTaskId)) as JsonObject;
      if (status.status === "completed") return status;
      if (status.status === "failed") {
        throw new Error(textValue(status.error_reason || status.message || "PDF 导出失败"));
      }
      await sleepMs(2000);
    }
    throw new Error("PDF生成时间较长，请稍后在导出记录中重试");
  }

  async function exportReport(format: "json" | "markdown" | "excel" | "pdf") {
    if (!projectId) return;
    const loadingKey = `export-${format}`;
    setExportingFormat(format);
    if (format === "pdf") {
      message.loading({ key: loadingKey, content: "PDF生成中，请稍后", duration: 0 });
    }
    try {
      let response = await api.exportReport(projectId, format);
      if (format === "pdf" && response.export_task_id && response.status !== "completed") {
        response = await waitForExportTask(String(response.export_task_id));
      }
      if (!response.download_url) {
        throw new Error(textValue(response.error_reason || "导出任务未返回下载地址"));
      }
      const suffix = format === "markdown" ? "md" : format === "excel" ? "xlsx" : format;
      await downloadWithAuth(String(response.download_url), `agentsim-${projectId}.${suffix}`);
      if (format === "pdf") {
        message.success({ key: loadingKey, content: "PDF导出已生成", duration: 2 });
      } else {
        message.success(`${format} 导出已生成`);
      }
    } catch (error) {
      const content = error instanceof Error ? error.message : "导出失败";
      if (format === "pdf") {
        message.error({ key: loadingKey, content, duration: 4 });
      } else {
        message.error(content);
      }
    } finally {
      setExportingFormat("");
    }
  }

  async function shareReport() {
    if (!projectId) return;
    try {
      const response = await api.shareReport(projectId);
      setShareUrl(String(response.frontend_share_url || response.share_url || ""));
      message.success("分享链接已创建");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "分享失败");
    }
  }

  const tabItems = [
    {
      key: "overview",
      label: "总览",
      children: (
        <Space direction="vertical" size={16} className="w-full">
          <MetricCards report={report} />
          {!pro && (
            <Alert
              type="info"
              showIcon
              icon={<LockOutlined />}
              message="当前项目按普通版创建，报告仅展示基础图表；导出、分享和竞品五维分析需要新建专业版项目。"
            />
          )}
          <Card className="nested-card" title="执行摘要">
            <Paragraph>{textValue(report.executive_summary || "报告尚未生成")}</Paragraph>
          </Card>
          <ReportNarrative report={report} />
          <ReportChartGrid report={report} pro={pro} />
        </Space>
      )
    },
    { key: "crowd", label: "人群分析", children: <CrowdAnalysis report={report} /> },
    { key: "social", label: "社交传播", children: <SocialPropagationAnalysis report={report} pro={pro} /> },
    ...(pro
      ? [
          { key: "strategy", label: "策略分析", children: <StrategyAnalysis report={report} /> },
          { key: "competitor", label: "竞品分析", children: <CompetitorAnalysis report={report} pro={pro} /> },
        ]
      : []),
    { key: "maut", label: "购买模型", children: <MautAnalysis report={report} /> },
    { key: "sensitivity", label: "敏感性", children: <SensitivityAnalysis report={report} pro={pro} /> },
    { key: "evidence", label: "RAG 证据", children: <EvidenceAnalysis report={report} /> }
  ];

  if (!projectId) return <Navigate to="/projects" replace />;

  return (
    <AppShell
      user={user}
      onLogout={onLogout}
      onUserChange={onUserChange}
      activeStep={4}
      sidebar={
        <ProjectSidebar
          project={project}
          assistantPage="step4"
          assistantContext={{
            report,
            plan_type: pro ? "pro" : "basic",
            share_url_created: Boolean(shareUrl)
          }}
        />
      }
    >
      <Card
        className="info-card report-card"
        title="Step4 查看报告"
        loading={loading}
        extra={
          <Space wrap>
            <Button icon={<ReloadOutlined />} onClick={loadReport}>
              刷新
            </Button>
            <Button icon={<CloudDownloadOutlined />} disabled={!pro || Boolean(exportingFormat)} loading={exportingFormat === "json"} onClick={() => exportReport("json")}>
              JSON
            </Button>
            <Button icon={<FileTextOutlined />} disabled={!pro || Boolean(exportingFormat)} loading={exportingFormat === "markdown"} onClick={() => exportReport("markdown")}>
              Markdown
            </Button>
            <Button icon={<BarChartOutlined />} disabled={!pro || Boolean(exportingFormat)} loading={exportingFormat === "excel"} onClick={() => exportReport("excel")}>
              Excel
            </Button>
            <Button icon={<FileTextOutlined />} disabled={!pro || Boolean(exportingFormat)} loading={exportingFormat === "pdf"} onClick={() => exportReport("pdf")}>
              PDF
            </Button>
            <Button type="primary" icon={<ShareAltOutlined />} disabled={!pro} onClick={shareReport}>
              分享
            </Button>
          </Space>
        }
      >
        {shareUrl && (
          <Alert
            className="mb-16"
            type="success"
            showIcon
            message="分享链接已生成"
            description={<Input readOnly value={shareUrl} onFocus={(event) => event.currentTarget.select()} />}
          />
        )}
        <Tabs items={tabItems} />
      </Card>
    </AppShell>
  );
}

function SharePage() {
  const { token } = useParams();
  const [payload, setPayload] = useState<JsonObject | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    api.getShare(token)
      .then(setPayload)
      .catch((err) => setError(err instanceof Error ? err.message : "分享链接不可用"));
  }, [token]);

  const report = (payload?.report || {}) as JsonObject;
  const pro = getChartData(report).plan_type === "pro";
  return (
    <Layout className="public-container">
      <Header className="navbar public-navbar">
        <div className="navbar-left">
          <PlatformLogo />
          <div>
            <div className="logo-title">智测公开报告</div>
            <div className="logo-subtitle">只读分享视图，不包含内部日志和 prompt 原文</div>
          </div>
        </div>
      </Header>
      <Content className="public-content">
        {error ? (
          <Alert type="error" showIcon message={error} />
        ) : (
          <Card className="info-card" title={textValue(payload?.project_name || "仿真报告")}>
            <MetricCards report={report} />
            <Divider />
            <Title level={4}>执行摘要</Title>
            <Paragraph>{textValue(report.executive_summary || "报告加载中")}</Paragraph>
            <Tabs
              items={[
                { key: "charts", label: "图表总览", children: <ReportChartGrid report={report} pro={pro} /> },
                { key: "crowd", label: "人群分析", children: <CrowdAnalysis report={report} /> },
                { key: "social", label: "社交传播", children: <SocialPropagationAnalysis report={report} pro={pro} /> },
                { key: "strategy", label: "策略分析", children: <StrategyAnalysis report={report} /> },
                { key: "evidence", label: "证据", children: <EvidenceAnalysis report={report} /> }
              ]}
            />
          </Card>
        )}
      </Content>
    </Layout>
  );
}

function PrintReportPage() {
  const { token } = useParams();
  const [payload, setPayload] = useState<JsonObject | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (window as Window & { __AGENTSIM_PRINT_READY?: boolean }).__AGENTSIM_PRINT_READY = false;
    if (!token) {
      setError("打印 token 缺失");
      return;
    }
    api.getPrintReport(token)
      .then((response) => setPayload(response))
      .catch((err) => setError(err instanceof Error ? err.message : "PDF 渲染报告不可用"));
  }, [token]);

  useEffect(() => {
    if (!payload && !error) return;
    let cancelled = false;
    waitForPrintAssets(error ? 300 : 1400).then(() => {
      if (!cancelled) {
        (window as Window & { __AGENTSIM_PRINT_READY?: boolean }).__AGENTSIM_PRINT_READY = true;
      }
    });
    return () => {
      cancelled = true;
    };
  }, [payload, error]);

  const report = (payload?.report || {}) as JsonObject;
  const pro = getChartData(report).plan_type === "pro";
  const generatedAt = textValue(payload?.generated_at || report.generated_at);

  return (
    <Layout className="print-container">
      <Header className="navbar print-navbar">
        <div className="navbar-left">
          <PlatformLogo />
          <div>
            <div className="logo-title">智测仿真报告</div>
            <div className="logo-subtitle">图表、证据与购买模型分析</div>
          </div>
        </div>
      </Header>
      <Content className="print-content">
        {error ? (
          <Alert type="error" showIcon message={error} />
        ) : (
          <Space direction="vertical" size={20} className="w-full print-report-stack">
            <section className="print-cover">
              <Text className="print-kicker">产品市场接受度仿真报告</Text>
              <Title level={1}>{textValue(payload?.project_name || "产品市场仿真报告")}</Title>
              <Paragraph>{textValue(report.executive_summary || "本报告基于产品配置、目标客群、竞品证据和多 Agent 社会模拟生成，用于辅助贵公司进行产品方案讨论。")}</Paragraph>
              <div className="print-meta-grid">
                <div>
                  <span>项目版本</span>
                  <strong>{pro ? "专业版" : "普通版"}</strong>
                </div>
                <div>
                  <span>报告状态</span>
                  <strong>{textValue(payload?.status || "completed")}</strong>
                </div>
                <div>
                  <span>导出时间</span>
                  <strong>{generatedAt ? formatDate(generatedAt) : "-"}</strong>
                </div>
              </div>
            </section>
            <MetricCards report={report} />
            <Card className="nested-card" title="执行摘要">
              <Paragraph>{textValue(report.executive_summary || "报告加载中")}</Paragraph>
            </Card>
            <ReportNarrative report={report} />
            <ReportChartGrid report={report} pro={pro} />
            <SocialPropagationAnalysis report={report} pro={pro} />
            <MautAnalysis report={report} />
            <SensitivityAnalysis report={report} pro={pro} />
            {pro && <CompetitorAnalysis report={report} pro={pro} />}
            <EvidenceAnalysis report={report} />
          </Space>
        )}
      </Content>
    </Layout>
  );
}

function AppRouter() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(Boolean(getToken()));

  async function loadMe() {
    if (!getToken()) {
      setChecking(false);
      return;
    }
    try {
      const response = (await api.me()) as User;
      setUser(response);
    } catch {
      clearToken();
      clearActiveProjectCache();
      setUser(null);
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => {
    loadMe();
  }, []);

  function logout() {
    clearToken();
    clearActiveProjectCache();
    setUser(null);
    window.location.href = "/login";
  }

  if (checking) return <div className="page-loading">正在初始化工作台...</div>;

  return (
    <Routes>
      <Route path="/login" element={<LoginPage onAuthed={setUser} />} />
      <Route path="/share/:token" element={<SharePage />} />
      <Route path="/print/:token" element={<PrintReportPage />} />
      <Route
        path="/projects"
        element={
          <Protected user={user}>
            <ProjectsPage user={user as User} onLogout={logout} onUserChange={setUser} />
          </Protected>
        }
      />
      <Route
        path="/step/1"
        element={
          <Protected user={user}>
            <Step1Product user={user as User} onLogout={logout} onUserChange={setUser} />
          </Protected>
        }
      />
      <Route
        path="/step/2"
        element={
          <Protected user={user}>
            <Step2Market user={user as User} onLogout={logout} onUserChange={setUser} />
          </Protected>
        }
      />
      <Route
        path="/step/3"
        element={
          <Protected user={user}>
            <Step3Simulate user={user as User} onLogout={logout} onUserChange={setUser} />
          </Protected>
        }
      />
      <Route
        path="/step/4"
        element={
          <Protected user={user}>
            <Step4Report user={user as User} onLogout={logout} onUserChange={setUser} />
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to={getToken() ? "/projects" : "/login"} replace />} />
    </Routes>
  );
}

function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: "#2563eb",
          borderRadius: 8,
          fontFamily: 'Inter, "Microsoft YaHei", "PingFang SC", Arial, sans-serif'
        }
      }}
    >
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
