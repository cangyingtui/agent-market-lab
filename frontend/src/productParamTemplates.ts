export type ProductParamControlType = "continuousSlider" | "discreteSelect" | "switch" | "steppedSlider" | "multiSelect";

export type ProductParamTemplate = {
  name: string;
  label: string;
  controlType: ProductParamControlType;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  options?: Array<string | number>;
  defaultValue?: unknown;
  defaultWeight: number;
  hint?: string;
};

export type ProductSubcategoryTemplate = {
  category: string;
  subcategory: string;
  aliases: string[];
  params: ProductParamTemplate[];
};

export const PRODUCT_MAJOR_CATEGORIES = [
  "消费电子",
  "家用电器",
  "智能硬件",
  "适老辅具",
  "个护健康",
  "母婴用品",
  "户外装备"
] as const;

export const PRODUCT_CATEGORY_MAP = {
  "消费电子": [
    "智能手机",
    "平板电脑",
    "笔记本电脑",
    "智能手表",
    "无线耳机",
    "游戏主机",
    "数码相机",
    "电子阅读器"
  ],
  "家用电器": [
    "空调",
    "冰箱",
    "洗衣机",
    "微波炉",
    "电饭煲",
    "扫地机器人",
    "空气净化器",
    "净水器"
  ],
  "智能硬件": [
    "智能音箱",
    "智能门锁",
    "智能灯具",
    "智能插座",
    "智能窗帘",
    "智能温控器",
    "安防摄像头",
    "健康监测仪"
  ],
  "适老辅具": [
    "助听器",
    "电动轮椅",
    "防跌倒监测器",
    "智能药盒",
    "起身辅助椅",
    "定位手环",
    "放大镜阅读器",
    "紧急呼叫器"
  ],
  "个护健康": [
    "电动牙刷",
    "冲牙器",
    "筋膜枪",
    "美容仪",
    "脱毛仪",
    "电子体温计",
    "血压计",
    "体脂秤"
  ],
  "母婴用品": [
    "婴儿监视器",
    "电动吸奶器",
    "智能温奶器",
    "儿童学习平板",
    "婴儿推车",
    "安全座椅",
    "早教机器人",
    "儿童手表"
  ],
  "户外装备": [
    "运动相机",
    "户外手表",
    "便携电源",
    "露营灯",
    "GPS导航仪",
    "对讲机",
    "防水背包",
    "应急手电"
  ]
} as const;

export const PRODUCT_PARAM_TEMPLATES: ProductSubcategoryTemplate[] = [
  {
    "category": "消费电子",
    "subcategory": "智能手机",
    "aliases": [],
    "params": [
      {
        "name": "屏幕尺寸",
        "label": "屏幕尺寸",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 5.4,
        "max": 7,
        "step": 0.1,
        "unit": "英寸",
        "defaultValue": 6.5
      },
      {
        "name": "电池容量",
        "label": "电池容量",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3000,
        "max": 6000,
        "step": 50,
        "unit": "mAh",
        "defaultValue": 4500
      },
      {
        "name": "摄像头像素",
        "label": "摄像头像素",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 12,
        "max": 200,
        "step": 1,
        "unit": "MP",
        "defaultValue": 50
      },
      {
        "name": "存储容量",
        "label": "存储容量",
        "controlType": "multiSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "128GB",
          "256GB",
          "512GB",
          "1TB"
        ],
        "defaultValue": [
          "256GB"
        ]
      },
      {
        "name": "刷新率",
        "label": "刷新率",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "60Hz",
          "90Hz",
          "120Hz"
        ],
        "defaultValue": "120Hz"
      },
      {
        "name": "处理器",
        "label": "处理器",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "旗舰",
          "中高端",
          "中端"
        ],
        "defaultValue": "中高端"
      },
      {
        "name": "快充功率",
        "label": "快充功率",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 20,
        "max": 150,
        "step": 1,
        "unit": "W",
        "defaultValue": 67
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IP53",
          "IP67",
          "IP68"
        ],
        "defaultValue": "IP68"
      }
    ]
  },
  {
    "category": "消费电子",
    "subcategory": "平板电脑",
    "aliases": [],
    "params": [
      {
        "name": "屏幕尺寸",
        "label": "屏幕尺寸",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 7.9,
        "max": 13,
        "step": 0.1,
        "unit": "英寸",
        "defaultValue": 11
      },
      {
        "name": "分辨率",
        "label": "分辨率",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "2K",
          "2.8K",
          "4K"
        ],
        "defaultValue": "2.8K"
      },
      {
        "name": "电池续航",
        "label": "电池续航",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 8,
        "max": 20,
        "step": 0.5,
        "unit": "小时",
        "defaultValue": 12
      },
      {
        "name": "存储容量",
        "label": "存储容量",
        "controlType": "multiSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "64GB",
          "128GB",
          "256GB",
          "512GB"
        ],
        "defaultValue": [
          "256GB"
        ]
      },
      {
        "name": "手写笔支持",
        "label": "手写笔支持",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      },
      {
        "name": "键盘配件",
        "label": "键盘配件",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "蜂窝版",
        "label": "蜂窝版",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "重量",
        "label": "重量",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 280,
        "max": 700,
        "step": 10,
        "unit": "g",
        "defaultValue": 450
      }
    ]
  },
  {
    "category": "消费电子",
    "subcategory": "笔记本电脑",
    "aliases": [],
    "params": [
      {
        "name": "屏幕尺寸",
        "label": "屏幕尺寸",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 13.3,
        "max": 17,
        "step": 0.1,
        "unit": "英寸",
        "defaultValue": 15.6
      },
      {
        "name": "处理器",
        "label": "处理器",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "i5",
          "i7",
          "i9",
          "R5",
          "R7",
          "R9"
        ],
        "defaultValue": "i7"
      },
      {
        "name": "内存",
        "label": "内存",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 8,
        "max": 64,
        "step": 8,
        "unit": "GB",
        "defaultValue": 16
      },
      {
        "name": "存储",
        "label": "存储",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 256,
        "max": 2048,
        "step": 256,
        "unit": "GB",
        "defaultValue": 512
      },
      {
        "name": "显卡",
        "label": "显卡",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "集成",
          "入门独显",
          "中端独显",
          "高端独显"
        ],
        "defaultValue": "中端独显"
      },
      {
        "name": "重量",
        "label": "重量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 0.9,
        "max": 2.5,
        "step": 0.1,
        "unit": "kg",
        "defaultValue": 1.5
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 6,
        "max": 20,
        "step": 0.5,
        "unit": "小时",
        "defaultValue": 10
      },
      {
        "name": "屏幕刷新率",
        "label": "屏幕刷新率",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "60Hz",
          "90Hz",
          "120Hz",
          "144Hz"
        ],
        "defaultValue": "120Hz"
      }
    ]
  },
  {
    "category": "消费电子",
    "subcategory": "智能手表",
    "aliases": [
      "智能手表/手环"
    ],
    "params": [
      {
        "name": "屏幕尺寸",
        "label": "屏幕尺寸",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1.2,
        "max": 2,
        "step": 0.1,
        "unit": "英寸",
        "defaultValue": 1.5
      },
      {
        "name": "续航时间",
        "label": "续航时间",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1,
        "max": 30,
        "step": 1,
        "unit": "天",
        "defaultValue": 14
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "steppedSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          1,
          2,
          3,
          4,
          5
        ],
        "unit": "级",
        "defaultValue": 4
      },
      {
        "name": "健康监测",
        "label": "健康监测",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "心率",
          "血氧",
          "睡眠",
          "压力",
          "ECG"
        ],
        "defaultValue": [
          "心率",
          "血氧",
          "睡眠"
        ]
      },
      {
        "name": "GPS定位",
        "label": "GPS定位",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "蜂窝网络",
        "label": "蜂窝网络",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "无"
      },
      {
        "name": "表壳材质",
        "label": "表壳材质",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "铝合金",
          "不锈钢",
          "钛合金"
        ],
        "defaultValue": "铝合金"
      },
      {
        "name": "运动模式",
        "label": "运动模式",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 10,
        "max": 150,
        "step": 5,
        "unit": "种",
        "defaultValue": 50
      }
    ]
  },
  {
    "category": "消费电子",
    "subcategory": "无线耳机",
    "aliases": [
      "真无线耳机"
    ],
    "params": [
      {
        "name": "续航（含充电盒）",
        "label": "续航（含充电盒）",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 15,
        "max": 60,
        "step": 1,
        "unit": "小时",
        "defaultValue": 30
      },
      {
        "name": "降噪类型",
        "label": "降噪类型",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无降噪",
          "被动降噪",
          "主动降噪"
        ],
        "defaultValue": "主动降噪"
      },
      {
        "name": "连接方式",
        "label": "连接方式",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "蓝牙5.0",
          "蓝牙5.3"
        ],
        "defaultValue": "蓝牙5.3"
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX4",
          "IPX5",
          "IPX7"
        ],
        "defaultValue": "IPX5"
      },
      {
        "name": "佩戴方式",
        "label": "佩戴方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "入耳式",
          "半入耳",
          "头戴式"
        ],
        "defaultValue": "入耳式"
      },
      {
        "name": "空间音频",
        "label": "空间音频",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      },
      {
        "name": "通话降噪",
        "label": "通话降噪",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "充电方式",
        "label": "充电方式",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有线",
          "无线",
          "无线+有线"
        ],
        "defaultValue": "无线+有线"
      }
    ]
  },
  {
    "category": "消费电子",
    "subcategory": "游戏主机",
    "aliases": [
      "游戏机"
    ],
    "params": [
      {
        "name": "存储容量",
        "label": "存储容量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 256,
        "max": 2048,
        "step": 256,
        "unit": "GB",
        "defaultValue": 1024
      },
      {
        "name": "画质输出",
        "label": "画质输出",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "1080P",
          "2K",
          "4K",
          "8K"
        ],
        "defaultValue": "4K"
      },
      {
        "name": "帧率支持",
        "label": "帧率支持",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "60fps",
          "120fps"
        ],
        "defaultValue": "120fps"
      },
      {
        "name": "手柄数量",
        "label": "手柄数量",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1,
        "max": 4,
        "step": 1,
        "unit": "个",
        "defaultValue": 2
      },
      {
        "name": "体感支持",
        "label": "体感支持",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "便携性",
        "label": "便携性",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "家用",
          "掌机",
          "混合"
        ],
        "defaultValue": "混合"
      },
      {
        "name": "在线服务",
        "label": "在线服务",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "向下兼容",
        "label": "向下兼容",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      }
    ]
  },
  {
    "category": "消费电子",
    "subcategory": "数码相机",
    "aliases": [
      "相机（含无人机）"
    ],
    "params": [
      {
        "name": "像素",
        "label": "像素",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 20,
        "max": 61,
        "step": 1,
        "unit": "MP",
        "defaultValue": 33
      },
      {
        "name": "传感器类型",
        "label": "传感器类型",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "APS-C",
          "全画幅",
          "中画幅"
        ],
        "defaultValue": "全画幅"
      },
      {
        "name": "防抖类型",
        "label": "防抖类型",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无机身防抖",
          "机身防抖",
          "镜头防抖"
        ],
        "defaultValue": "机身防抖"
      },
      {
        "name": "视频拍摄",
        "label": "视频拍摄",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "1080P",
          "4K 30fps",
          "4K 60fps",
          "8K"
        ],
        "defaultValue": "4K 60fps"
      },
      {
        "name": "对焦系统",
        "label": "对焦系统",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "反差",
          "相位",
          "混合"
        ],
        "defaultValue": "混合"
      },
      {
        "name": "连拍速度",
        "label": "连拍速度",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 30,
        "step": 1,
        "unit": "张/秒",
        "defaultValue": 10
      },
      {
        "name": "取景器类型",
        "label": "取景器类型",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "电子取景",
          "光学取景"
        ],
        "defaultValue": "电子取景"
      },
      {
        "name": "翻转屏",
        "label": "翻转屏",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "支持"
      }
    ]
  },
  {
    "category": "消费电子",
    "subcategory": "电子阅读器",
    "aliases": [],
    "params": [
      {
        "name": "屏幕尺寸",
        "label": "屏幕尺寸",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 6,
        "max": 10.3,
        "step": 0.1,
        "unit": "英寸",
        "defaultValue": 7
      },
      {
        "name": "分辨率",
        "label": "分辨率",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "212",
          "300",
          "400 PPI"
        ],
        "defaultValue": "300 PPI"
      },
      {
        "name": "内存",
        "label": "内存",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "8GB",
          "16GB",
          "32GB",
          "64GB"
        ],
        "defaultValue": "16GB"
      },
      {
        "name": "电池续航",
        "label": "电池续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 10,
        "max": 50,
        "step": 1,
        "unit": "天",
        "defaultValue": 30
      },
      {
        "name": "背光调节",
        "label": "背光调节",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "冷光",
          "冷暖双色"
        ],
        "defaultValue": "冷暖双色"
      },
      {
        "name": "手写笔",
        "label": "手写笔",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      },
      {
        "name": "防水",
        "label": "防水",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "IPX3",
          "IPX8"
        ],
        "defaultValue": "IPX8"
      },
      {
        "name": "格式支持",
        "label": "格式支持",
        "controlType": "multiSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "EPUB",
          "PDF",
          "MOBI",
          "TXT"
        ],
        "defaultValue": [
          "EPUB",
          "PDF"
        ]
      }
    ]
  },
  {
    "category": "家用电器",
    "subcategory": "空调",
    "aliases": [],
    "params": [
      {
        "name": "制冷功率",
        "label": "制冷功率",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "1匹",
          "1.5匹",
          "2匹",
          "3匹"
        ],
        "defaultValue": "1.5匹"
      },
      {
        "name": "能效等级",
        "label": "能效等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "一级",
          "二级",
          "三级"
        ],
        "defaultValue": "一级"
      },
      {
        "name": "制冷剂",
        "label": "制冷剂",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "R22",
          "R32",
          "R410a"
        ],
        "defaultValue": "R32"
      },
      {
        "name": "变频类型",
        "label": "变频类型",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "定频",
          "变频",
          "全直流变频"
        ],
        "defaultValue": "全直流变频"
      },
      {
        "name": "噪音",
        "label": "噪音",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 18,
        "max": 42,
        "step": 1,
        "unit": "dB",
        "defaultValue": 24
      },
      {
        "name": "联网控制",
        "label": "联网控制",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      },
      {
        "name": "自清洁",
        "label": "自清洁",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      },
      {
        "name": "制冷面积",
        "label": "制冷面积",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 10,
        "max": 60,
        "step": 1,
        "unit": "㎡",
        "defaultValue": 25
      }
    ]
  },
  {
    "category": "家用电器",
    "subcategory": "冰箱",
    "aliases": [],
    "params": [
      {
        "name": "容量",
        "label": "容量",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 100,
        "max": 800,
        "step": 10,
        "unit": "L",
        "defaultValue": 450
      },
      {
        "name": "能效等级",
        "label": "能效等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "一级",
          "二级",
          "三级"
        ],
        "defaultValue": "一级"
      },
      {
        "name": "制冷方式",
        "label": "制冷方式",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "直冷",
          "风冷",
          "风直冷混合"
        ],
        "defaultValue": "风冷"
      },
      {
        "name": "循环系统",
        "label": "循环系统",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "单循环",
          "双循环",
          "三循环"
        ],
        "defaultValue": "双循环"
      },
      {
        "name": "变温室",
        "label": "变温室",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "除菌净味",
        "label": "除菌净味",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "面板材质",
        "label": "面板材质",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "钣金",
          "PCM",
          "VCM",
          "玻璃"
        ],
        "defaultValue": "玻璃"
      },
      {
        "name": "压缩机",
        "label": "压缩机",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "定频",
          "变频"
        ],
        "defaultValue": "变频"
      }
    ]
  },
  {
    "category": "家用电器",
    "subcategory": "洗衣机",
    "aliases": [
      "洗衣机/烘干机"
    ],
    "params": [
      {
        "name": "容量",
        "label": "容量",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "8kg",
          "10kg",
          "12kg"
        ],
        "defaultValue": "10kg"
      },
      {
        "name": "能效等级",
        "label": "能效等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "一级",
          "二级",
          "三级"
        ],
        "defaultValue": "一级"
      },
      {
        "name": "电机类型",
        "label": "电机类型",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "皮带",
          "DD直驱"
        ],
        "defaultValue": "DD直驱"
      },
      {
        "name": "烘干功能",
        "label": "烘干功能",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "冷凝烘干",
          "热泵烘干"
        ],
        "defaultValue": "热泵烘干"
      },
      {
        "name": "除菌方式",
        "label": "除菌方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "高温",
          "银离子",
          "紫外线"
        ],
        "defaultValue": "紫外线"
      },
      {
        "name": "智能投放",
        "label": "智能投放",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "噪音",
        "label": "噪音",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 48,
        "max": 62,
        "step": 1,
        "unit": "dB",
        "defaultValue": 52
      },
      {
        "name": "内筒材质",
        "label": "内筒材质",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "不锈钢",
          "钻石内筒"
        ],
        "defaultValue": "不锈钢"
      }
    ]
  },
  {
    "category": "家用电器",
    "subcategory": "微波炉",
    "aliases": [
      "微波炉/烤箱/蒸烤箱"
    ],
    "params": [
      {
        "name": "容量",
        "label": "容量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 17,
        "max": 32,
        "step": 1,
        "unit": "L",
        "defaultValue": 23
      },
      {
        "name": "功率",
        "label": "功率",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 700,
        "max": 1000,
        "step": 10,
        "unit": "W",
        "defaultValue": 800
      },
      {
        "name": "加热方式",
        "label": "加热方式",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "转盘式",
          "平板式"
        ],
        "defaultValue": "平板式"
      },
      {
        "name": "变频技术",
        "label": "变频技术",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "烧烤功能",
        "label": "烧烤功能",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "蒸汽功能",
        "label": "蒸汽功能",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "无"
      },
      {
        "name": "操控方式",
        "label": "操控方式",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "旋钮",
          "按键",
          "触屏"
        ],
        "defaultValue": "触屏"
      },
      {
        "name": "内胆材质",
        "label": "内胆材质",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "涂层",
          "不锈钢",
          "陶瓷"
        ],
        "defaultValue": "不锈钢"
      }
    ]
  },
  {
    "category": "家用电器",
    "subcategory": "电饭煲",
    "aliases": [
      "电饭煲/压力锅"
    ],
    "params": [
      {
        "name": "容量",
        "label": "容量",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "2L",
          "3L",
          "4L",
          "5L"
        ],
        "defaultValue": "4L"
      },
      {
        "name": "加热方式",
        "label": "加热方式",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "底盘加热",
          "IH电磁加热"
        ],
        "defaultValue": "IH电磁加热"
      },
      {
        "name": "内胆材质",
        "label": "内胆材质",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "铝合金",
          "不锈钢",
          "陶瓷",
          "铁釜"
        ],
        "defaultValue": "铁釜"
      },
      {
        "name": "压力烹饪",
        "label": "压力烹饪",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "预约功能",
        "label": "预约功能",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "多功能菜单",
        "label": "多功能菜单",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 5,
        "max": 24,
        "step": 1,
        "unit": "种",
        "defaultValue": 12
      },
      {
        "name": "拆卸清洗",
        "label": "拆卸清洗",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "不可拆",
          "上盖可拆",
          "全拆"
        ],
        "defaultValue": "上盖可拆"
      },
      {
        "name": "保温时长",
        "label": "保温时长",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 6,
        "max": 24,
        "step": 1,
        "unit": "小时",
        "defaultValue": 12
      }
    ]
  },
  {
    "category": "家用电器",
    "subcategory": "扫地机器人",
    "aliases": [],
    "params": [
      {
        "name": "吸力",
        "label": "吸力",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 2000,
        "max": 8000,
        "step": 100,
        "unit": "Pa",
        "defaultValue": 5000
      },
      {
        "name": "导航方式",
        "label": "导航方式",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "陀螺仪",
          "视觉",
          "激光"
        ],
        "defaultValue": "激光"
      },
      {
        "name": "避障能力",
        "label": "避障能力",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "机械",
          "红外",
          "3D结构光"
        ],
        "defaultValue": "3D结构光"
      },
      {
        "name": "集尘方式",
        "label": "集尘方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "手动",
          "自动集尘"
        ],
        "defaultValue": "自动集尘"
      },
      {
        "name": "拖地功能",
        "label": "拖地功能",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "普通拖地",
          "旋转加压"
        ],
        "defaultValue": "旋转加压"
      },
      {
        "name": "水箱容量",
        "label": "水箱容量",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 150,
        "max": 400,
        "step": 10,
        "unit": "ml",
        "defaultValue": 250
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 60,
        "max": 180,
        "step": 10,
        "unit": "分钟",
        "defaultValue": 120
      },
      {
        "name": "地毯识别",
        "label": "地毯识别",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "家用电器",
    "subcategory": "空气净化器",
    "aliases": [],
    "params": [
      {
        "name": "CADR值",
        "label": "CADR值",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 200,
        "max": 800,
        "step": 10,
        "unit": "m³/h",
        "defaultValue": 500
      },
      {
        "name": "适用面积",
        "label": "适用面积",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 20,
        "max": 96,
        "step": 1,
        "unit": "㎡",
        "defaultValue": 50
      },
      {
        "name": "颗粒物CCM",
        "label": "颗粒物CCM",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "P1",
          "P2",
          "P3",
          "P4"
        ],
        "defaultValue": "P4"
      },
      {
        "name": "甲醛CCM",
        "label": "甲醛CCM",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "F1",
          "F2",
          "F3",
          "F4"
        ],
        "defaultValue": "F4"
      },
      {
        "name": "噪音",
        "label": "噪音",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 32,
        "max": 66,
        "step": 1,
        "unit": "dB",
        "defaultValue": 35
      },
      {
        "name": "净化方式",
        "label": "净化方式",
        "controlType": "multiSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "HEPA",
          "活性炭",
          "负离子",
          "紫外"
        ],
        "defaultValue": [
          "HEPA",
          "活性炭"
        ]
      },
      {
        "name": "联网控制",
        "label": "联网控制",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "滤芯更换提醒",
        "label": "滤芯更换提醒",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "家用电器",
    "subcategory": "净水器",
    "aliases": [],
    "params": [
      {
        "name": "过滤精度",
        "label": "过滤精度",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 0.0001,
        "max": 0.01,
        "step": 0.0001,
        "unit": "μm",
        "defaultValue": 0.0001
      },
      {
        "name": "通量",
        "label": "通量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 400,
        "max": 1200,
        "step": 50,
        "unit": "GPD",
        "defaultValue": 600
      },
      {
        "name": "滤芯寿命",
        "label": "滤芯寿命",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 6,
        "max": 36,
        "step": 1,
        "unit": "个月",
        "defaultValue": 24
      },
      {
        "name": "废水比",
        "label": "废水比",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "1:1",
          "1.5:1",
          "2:1",
          "3:1"
        ],
        "defaultValue": "2:1"
      },
      {
        "name": "智能提醒",
        "label": "智能提醒",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "即热功能",
        "label": "即热功能",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "无"
      },
      {
        "name": "双出水",
        "label": "双出水",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "外观材质",
        "label": "外观材质",
        "controlType": "discreteSelect",
        "defaultWeight": 2,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "不锈钢",
          "钢化玻璃",
          "塑料"
        ],
        "defaultValue": "钢化玻璃"
      }
    ]
  },
  {
    "category": "智能硬件",
    "subcategory": "智能音箱",
    "aliases": [],
    "params": [
      {
        "name": "扬声器功率",
        "label": "扬声器功率",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 5,
        "max": 50,
        "step": 1,
        "unit": "W",
        "defaultValue": 20
      },
      {
        "name": "音质认证",
        "label": "音质认证",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "Hi-Res",
          "杜比全景声"
        ],
        "defaultValue": "Hi-Res"
      },
      {
        "name": "屏幕显示",
        "label": "屏幕显示",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无屏",
          "LED点阵",
          "触摸屏"
        ],
        "defaultValue": "触摸屏"
      },
      {
        "name": "语音助手",
        "label": "语音助手",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "小爱",
          "小度",
          "天猫精灵",
          "其他"
        ],
        "defaultValue": "小爱"
      },
      {
        "name": "智能家居控制",
        "label": "智能家居控制",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      },
      {
        "name": "连接方式",
        "label": "连接方式",
        "controlType": "multiSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "Wi-Fi",
          "蓝牙",
          "AUX"
        ],
        "defaultValue": [
          "Wi-Fi",
          "蓝牙"
        ]
      },
      {
        "name": "麦克风数量",
        "label": "麦克风数量",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 2,
        "max": 7,
        "step": 1,
        "unit": "个",
        "defaultValue": 4
      },
      {
        "name": "立体声配对",
        "label": "立体声配对",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      }
    ]
  },
  {
    "category": "智能硬件",
    "subcategory": "智能门锁",
    "aliases": [],
    "params": [
      {
        "name": "开锁方式",
        "label": "开锁方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "指纹",
          "密码",
          "卡片",
          "钥匙",
          "人脸",
          "手机"
        ],
        "defaultValue": [
          "指纹",
          "密码",
          "钥匙",
          "手机"
        ]
      },
      {
        "name": "安全等级",
        "label": "安全等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "B级",
          "C级",
          "C+级"
        ],
        "defaultValue": "C级"
      },
      {
        "name": "联网方式",
        "label": "联网方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "Wi-Fi",
          "蓝牙",
          "Zigbee"
        ],
        "defaultValue": "Wi-Fi"
      },
      {
        "name": "电池续航",
        "label": "电池续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 6,
        "max": 18,
        "step": 1,
        "unit": "个月",
        "defaultValue": 12
      },
      {
        "name": "猫眼功能",
        "label": "猫眼功能",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "防撬报警",
        "label": "防撬报警",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "材质",
        "label": "材质",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "锌合金",
          "铝合金",
          "不锈钢"
        ],
        "defaultValue": "锌合金"
      },
      {
        "name": "天地钩",
        "label": "天地钩",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      }
    ]
  },
  {
    "category": "智能硬件",
    "subcategory": "智能灯具",
    "aliases": [],
    "params": [
      {
        "name": "功率",
        "label": "功率",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 5,
        "max": 50,
        "step": 1,
        "unit": "W",
        "defaultValue": 20
      },
      {
        "name": "色温",
        "label": "色温",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 2700,
        "max": 6500,
        "step": 50,
        "unit": "K",
        "defaultValue": 4000
      },
      {
        "name": "亮度",
        "label": "亮度",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 200,
        "max": 3000,
        "step": 50,
        "unit": "lm",
        "defaultValue": 1200
      },
      {
        "name": "控制方式",
        "label": "控制方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "手机",
          "语音",
          "遥控",
          "墙壁开关"
        ],
        "defaultValue": [
          "手机",
          "语音",
          "墙壁开关"
        ]
      },
      {
        "name": "色彩",
        "label": "色彩",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "单色",
          "双色",
          "RGB全彩"
        ],
        "defaultValue": "RGB全彩"
      },
      {
        "name": "定时功能",
        "label": "定时功能",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "场景联动",
        "label": "场景联动",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "Ra显色指数",
        "label": "Ra显色指数",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 80,
        "max": 98,
        "step": 1,
        "unit": "",
        "defaultValue": 90
      }
    ]
  },
  {
    "category": "智能硬件",
    "subcategory": "智能插座",
    "aliases": [
      "智能插座/开关"
    ],
    "params": [
      {
        "name": "最大功率",
        "label": "最大功率",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 2000,
        "max": 4000,
        "step": 100,
        "unit": "W",
        "defaultValue": 2500
      },
      {
        "name": "联网方式",
        "label": "联网方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "Wi-Fi",
          "蓝牙",
          "Zigbee"
        ],
        "defaultValue": "Wi-Fi"
      },
      {
        "name": "USB口",
        "label": "USB口",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "1个",
          "2个"
        ],
        "defaultValue": "2个"
      },
      {
        "name": "电量统计",
        "label": "电量统计",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "定时开关",
        "label": "定时开关",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "过载保护",
        "label": "过载保护",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "语音控制",
        "label": "语音控制",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "体积大小",
        "label": "体积大小",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "迷你",
          "标准",
          "加大"
        ],
        "defaultValue": "标准"
      }
    ]
  },
  {
    "category": "智能硬件",
    "subcategory": "智能窗帘",
    "aliases": [
      "智能窗帘电机"
    ],
    "params": [
      {
        "name": "电机类型",
        "label": "电机类型",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "交流",
          "直流"
        ],
        "defaultValue": "直流"
      },
      {
        "name": "运行噪音",
        "label": "运行噪音",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 25,
        "max": 45,
        "step": 1,
        "unit": "dB",
        "defaultValue": 30
      },
      {
        "name": "承重",
        "label": "承重",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 30,
        "max": 80,
        "step": 5,
        "unit": "kg",
        "defaultValue": 50
      },
      {
        "name": "控制方式",
        "label": "控制方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "遥控",
          "手机",
          "语音",
          "定时"
        ],
        "defaultValue": [
          "手机",
          "语音",
          "定时"
        ]
      },
      {
        "name": "手拉启动",
        "label": "手拉启动",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      },
      {
        "name": "轨道类型",
        "label": "轨道类型",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "直轨",
          "L型",
          "U型"
        ],
        "defaultValue": "直轨"
      },
      {
        "name": "电池供电",
        "label": "电池供电",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "无"
      },
      {
        "name": "开合比例",
        "label": "开合比例",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      }
    ]
  },
  {
    "category": "智能硬件",
    "subcategory": "智能温控器",
    "aliases": [],
    "params": [
      {
        "name": "控温精度",
        "label": "控温精度",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 0.5,
        "max": 3,
        "step": 0.5,
        "unit": "℃",
        "defaultValue": 1
      },
      {
        "name": "控制方式",
        "label": "控制方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "触屏",
          "手机",
          "语音",
          "编程"
        ],
        "defaultValue": [
          "手机",
          "触屏",
          "编程"
        ]
      },
      {
        "name": "兼容系统",
        "label": "兼容系统",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "水暖",
          "电暖",
          "风暖",
          "多系统"
        ],
        "defaultValue": "水暖"
      },
      {
        "name": "学习功能",
        "label": "学习功能",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "屏幕类型",
        "label": "屏幕类型",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "LCD",
          "OLED",
          "电子墨水"
        ],
        "defaultValue": "OLED"
      },
      {
        "name": "传感器",
        "label": "传感器",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "单温",
          "温湿度",
          "温湿+人体"
        ],
        "defaultValue": "温湿+人体"
      },
      {
        "name": "安装方式",
        "label": "安装方式",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "壁挂",
          "桌面",
          "两用"
        ],
        "defaultValue": "壁挂"
      },
      {
        "name": "联动设备",
        "label": "联动设备",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1,
        "max": 20,
        "step": 1,
        "unit": "个",
        "defaultValue": 8
      }
    ]
  },
  {
    "category": "智能硬件",
    "subcategory": "安防摄像头",
    "aliases": [
      "智能摄像头（室内/室外）"
    ],
    "params": [
      {
        "name": "分辨率",
        "label": "分辨率",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "1080P",
          "2K",
          "4K"
        ],
        "defaultValue": "2K"
      },
      {
        "name": "夜视类型",
        "label": "夜视类型",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "红外",
          "全彩",
          "红外+全彩"
        ],
        "defaultValue": "红外+全彩"
      },
      {
        "name": "云台旋转",
        "label": "云台旋转",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "固定",
          "水平",
          "水平+垂直"
        ],
        "defaultValue": "水平+垂直"
      },
      {
        "name": "存储方式",
        "label": "存储方式",
        "controlType": "multiSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "本地存储",
          "云存储",
          "NVR"
        ],
        "defaultValue": [
          "本地",
          "云存储"
        ]
      },
      {
        "name": "AI检测",
        "label": "AI检测",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "人形",
          "移动",
          "声音",
          "宠物"
        ],
        "defaultValue": [
          "人形",
          "移动"
        ]
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "室内",
          "IP65",
          "IP67"
        ],
        "defaultValue": "IP67"
      },
      {
        "name": "双向通话",
        "label": "双向通话",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "安装方式",
        "label": "安装方式",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "壁挂",
          "吸顶",
          "桌面"
        ],
        "defaultValue": "壁挂"
      }
    ]
  },
  {
    "category": "智能硬件",
    "subcategory": "健康监测仪",
    "aliases": [],
    "params": [
      {
        "name": "监测项目",
        "label": "监测项目",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "血压",
          "血氧",
          "心率",
          "体温",
          "血糖"
        ],
        "defaultValue": [
          "血压",
          "血氧",
          "心率"
        ]
      },
      {
        "name": "测量精度",
        "label": "测量精度",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "医疗级",
          "家用准医疗",
          "家用"
        ],
        "defaultValue": "家用准医疗"
      },
      {
        "name": "数据同步",
        "label": "数据同步",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "蓝牙",
          "Wi-Fi",
          "蓝牙+Wi-Fi"
        ],
        "defaultValue": "蓝牙+Wi-Fi"
      },
      {
        "name": "屏幕类型",
        "label": "屏幕类型",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无屏",
          "LED",
          "彩屏"
        ],
        "defaultValue": "彩屏"
      },
      {
        "name": "多用户",
        "label": "多用户",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      },
      {
        "name": "APP报告",
        "label": "APP报告",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      },
      {
        "name": "电池续航",
        "label": "电池续航",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 30,
        "step": 1,
        "unit": "天",
        "defaultValue": 7
      },
      {
        "name": "语音播报",
        "label": "语音播报",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "适老辅具",
    "subcategory": "助听器",
    "aliases": [],
    "params": [
      {
        "name": "通道数",
        "label": "通道数",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 2,
        "max": 24,
        "step": 1,
        "unit": "通道",
        "defaultValue": 12
      },
      {
        "name": "降噪等级",
        "label": "降噪等级",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1,
        "max": 5,
        "step": 1,
        "unit": "级",
        "defaultValue": 4
      },
      {
        "name": "啸叫抑制",
        "label": "啸叫抑制",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "佩戴方式",
        "label": "佩戴方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "耳背式",
          "耳内式",
          "耳道式"
        ],
        "defaultValue": "耳内式"
      },
      {
        "name": "电池续航",
        "label": "电池续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 20,
        "max": 120,
        "step": 5,
        "unit": "小时",
        "defaultValue": 80
      },
      {
        "name": "蓝牙连接",
        "label": "蓝牙连接",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "防水防汗",
        "label": "防水防汗",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX4",
          "IPX5",
          "IPX7"
        ],
        "defaultValue": "IPX5"
      },
      {
        "name": "APP调节",
        "label": "APP调节",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "适老辅具",
    "subcategory": "电动轮椅",
    "aliases": [
      "轮椅（手动/电动）"
    ],
    "params": [
      {
        "name": "续航里程",
        "label": "续航里程",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 10,
        "max": 50,
        "step": 1,
        "unit": "km",
        "defaultValue": 25
      },
      {
        "name": "承重",
        "label": "承重",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 100,
        "max": 150,
        "step": 5,
        "unit": "kg",
        "defaultValue": 120
      },
      {
        "name": "折叠方式",
        "label": "折叠方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "手动折叠",
          "电动折叠"
        ],
        "defaultValue": "电动折叠"
      },
      {
        "name": "电机功率",
        "label": "电机功率",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 200,
        "max": 800,
        "step": 20,
        "unit": "W",
        "defaultValue": 500
      },
      {
        "name": "爬坡能力",
        "label": "爬坡能力",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 6,
        "max": 15,
        "step": 1,
        "unit": "度",
        "defaultValue": 10
      },
      {
        "name": "座宽",
        "label": "座宽",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 40,
        "max": 55,
        "step": 1,
        "unit": "cm",
        "defaultValue": 45
      },
      {
        "name": "控制器",
        "label": "控制器",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "摇杆",
          "按键",
          "气控"
        ],
        "defaultValue": "摇杆"
      },
      {
        "name": "避障功能",
        "label": "避障功能",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "适老辅具",
    "subcategory": "防跌倒监测器",
    "aliases": [
      "跌倒报警器/老人手机"
    ],
    "params": [
      {
        "name": "监测方式",
        "label": "监测方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "加速度",
          "气压",
          "姿态融合"
        ],
        "defaultValue": [
          "姿态融合"
        ]
      },
      {
        "name": "报警方式",
        "label": "报警方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "APP推送",
          "短信",
          "电话",
          "声光"
        ],
        "defaultValue": [
          "APP推送",
          "短信",
          "电话"
        ]
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 30,
        "step": 1,
        "unit": "天",
        "defaultValue": 15
      },
      {
        "name": "误报率",
        "label": "误报率",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1,
        "max": 10,
        "step": 1,
        "unit": "%",
        "defaultValue": 3
      },
      {
        "name": "佩戴方式",
        "label": "佩戴方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "挂脖",
          "腰带",
          "手环"
        ],
        "defaultValue": "挂脖"
      },
      {
        "name": "防水",
        "label": "防水",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX4",
          "IPX5",
          "IPX7"
        ],
        "defaultValue": "IPX7"
      },
      {
        "name": "GPS定位",
        "label": "GPS定位",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "双向通话",
        "label": "双向通话",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "适老辅具",
    "subcategory": "智能药盒",
    "aliases": [],
    "params": [
      {
        "name": "格子数量",
        "label": "格子数量",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 4,
        "max": 28,
        "step": 2,
        "unit": "格",
        "defaultValue": 14
      },
      {
        "name": "提醒方式",
        "label": "提醒方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "声",
          "光",
          "APP",
          "短信"
        ],
        "defaultValue": [
          "声",
          "光",
          "APP"
        ]
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 7,
        "max": 90,
        "step": 1,
        "unit": "天",
        "defaultValue": 30
      },
      {
        "name": "药物互斥提醒",
        "label": "药物互斥提醒",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "家人远程查看",
        "label": "家人远程查看",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "药盒材质",
        "label": "药盒材质",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "塑料",
          "不锈钢",
          "食品级硅胶"
        ],
        "defaultValue": "食品级硅胶"
      },
      {
        "name": "便携性",
        "label": "便携性",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "家用",
          "便携",
          "两用"
        ],
        "defaultValue": "两用"
      },
      {
        "name": "语音播报",
        "label": "语音播报",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "适老辅具",
    "subcategory": "起身辅助椅",
    "aliases": [],
    "params": [
      {
        "name": "承重",
        "label": "承重",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 100,
        "max": 180,
        "step": 5,
        "unit": "kg",
        "defaultValue": 130
      },
      {
        "name": "起坐角度",
        "label": "起坐角度",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 30,
        "max": 75,
        "step": 5,
        "unit": "度",
        "defaultValue": 55
      },
      {
        "name": "驱动方式",
        "label": "驱动方式",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "液压",
          "电动"
        ],
        "defaultValue": "电动"
      },
      {
        "name": "面料",
        "label": "面料",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "布艺",
          "皮革",
          "科技布"
        ],
        "defaultValue": "科技布"
      },
      {
        "name": "扶手设计",
        "label": "扶手设计",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "固定",
          "可翻转",
          "可升降"
        ],
        "defaultValue": "可翻转"
      },
      {
        "name": "按摩功能",
        "label": "按摩功能",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "加热功能",
        "label": "加热功能",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "遥控操作",
        "label": "遥控操作",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "适老辅具",
    "subcategory": "定位手环",
    "aliases": [],
    "params": [
      {
        "name": "定位方式",
        "label": "定位方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "GPS",
          "北斗",
          "Wi-Fi",
          "基站"
        ],
        "defaultValue": [
          "GPS",
          "北斗",
          "Wi-Fi"
        ]
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 15,
        "step": 1,
        "unit": "天",
        "defaultValue": 7
      },
      {
        "name": "电子围栏",
        "label": "电子围栏",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "SOS按钮",
        "label": "SOS按钮",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "防水",
        "label": "防水",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX4",
          "IPX5",
          "IPX7"
        ],
        "defaultValue": "IPX7"
      },
      {
        "name": "健康监测",
        "label": "健康监测",
        "controlType": "multiSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "心率",
          "血压",
          "体温"
        ],
        "defaultValue": [
          "心率"
        ]
      },
      {
        "name": "双向通话",
        "label": "双向通话",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "佩戴材质",
        "label": "佩戴材质",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "硅胶",
          "TPU",
          "编织"
        ],
        "defaultValue": "硅胶"
      }
    ]
  },
  {
    "category": "适老辅具",
    "subcategory": "放大镜阅读器",
    "aliases": [],
    "params": [
      {
        "name": "放大倍数",
        "label": "放大倍数",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 2,
        "max": 32,
        "step": 1,
        "unit": "倍",
        "defaultValue": 8
      },
      {
        "name": "屏幕尺寸",
        "label": "屏幕尺寸",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3.5,
        "max": 12,
        "step": 0.5,
        "unit": "英寸",
        "defaultValue": 7
      },
      {
        "name": "色彩模式",
        "label": "色彩模式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "黑白",
          "真彩",
          "反色",
          "多模式"
        ],
        "defaultValue": "多模式"
      },
      {
        "name": "语音朗读",
        "label": "语音朗读",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "冻结画面",
        "label": "冻结画面",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 8,
        "step": 0.5,
        "unit": "小时",
        "defaultValue": 5
      },
      {
        "name": "便携性",
        "label": "便携性",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "手持式",
          "台式",
          "折叠"
        ],
        "defaultValue": "折叠"
      },
      {
        "name": "存储截图",
        "label": "存储截图",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "适老辅具",
    "subcategory": "紧急呼叫器",
    "aliases": [],
    "params": [
      {
        "name": "触发方式",
        "label": "触发方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "按键",
          "拉绳",
          "语音",
          "跌倒自动"
        ],
        "defaultValue": [
          "按键",
          "拉绳",
          "跌倒自动"
        ]
      },
      {
        "name": "通讯方式",
        "label": "通讯方式",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "Wi-Fi",
          "4G",
          "双模"
        ],
        "defaultValue": "双模"
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 12,
        "max": 72,
        "step": 2,
        "unit": "小时",
        "defaultValue": 48
      },
      {
        "name": "防水",
        "label": "防水",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX4",
          "IPX5",
          "IPX7"
        ],
        "defaultValue": "IPX7"
      },
      {
        "name": "呼叫对象",
        "label": "呼叫对象",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1,
        "max": 10,
        "step": 1,
        "unit": "个",
        "defaultValue": 5
      },
      {
        "name": "双向通话",
        "label": "双向通话",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "佩戴方式",
        "label": "佩戴方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "挂脖",
          "手环",
          "壁挂"
        ],
        "defaultValue": "挂脖"
      },
      {
        "name": "音量",
        "label": "音量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 70,
        "max": 100,
        "step": 1,
        "unit": "dB",
        "defaultValue": 85
      }
    ]
  },
  {
    "category": "个护健康",
    "subcategory": "电动牙刷",
    "aliases": [],
    "params": [
      {
        "name": "震动频率",
        "label": "震动频率",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 20000,
        "max": 42000,
        "step": 500,
        "unit": "次/分",
        "defaultValue": 31000
      },
      {
        "name": "清洁模式",
        "label": "清洁模式",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 8,
        "step": 1,
        "unit": "种",
        "defaultValue": 5
      },
      {
        "name": "刷头类型",
        "label": "刷头类型",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "杜邦",
          "竹炭",
          "硅胶"
        ],
        "defaultValue": "杜邦"
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX5",
          "IPX7",
          "IPX8"
        ],
        "defaultValue": "IPX7"
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 7,
        "max": 90,
        "step": 1,
        "unit": "天",
        "defaultValue": 30
      },
      {
        "name": "充电方式",
        "label": "充电方式",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "底座",
          "Type-C",
          "感应"
        ],
        "defaultValue": "感应"
      },
      {
        "name": "压力感应",
        "label": "压力感应",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "智能提醒",
        "label": "智能提醒",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "个护健康",
    "subcategory": "冲牙器",
    "aliases": [],
    "params": [
      {
        "name": "水压档位",
        "label": "水压档位",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 10,
        "step": 1,
        "unit": "档",
        "defaultValue": 5
      },
      {
        "name": "水箱容量",
        "label": "水箱容量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 150,
        "max": 350,
        "step": 10,
        "unit": "ml",
        "defaultValue": 250
      },
      {
        "name": "脉冲频率",
        "label": "脉冲频率",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1200,
        "max": 1800,
        "step": 50,
        "unit": "次/分",
        "defaultValue": 1400
      },
      {
        "name": "喷嘴数量",
        "label": "喷嘴数量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 2,
        "max": 8,
        "step": 1,
        "unit": "个",
        "defaultValue": 5
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX5",
          "IPX7",
          "IPX8"
        ],
        "defaultValue": "IPX7"
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 10,
        "max": 90,
        "step": 1,
        "unit": "天",
        "defaultValue": 30
      },
      {
        "name": "便携性",
        "label": "便携性",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "家用",
          "便携",
          "两用"
        ],
        "defaultValue": "两用"
      },
      {
        "name": "模式切换",
        "label": "模式切换",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "按键",
          "旋钮",
          "触控"
        ],
        "defaultValue": "按键"
      }
    ]
  },
  {
    "category": "个护健康",
    "subcategory": "筋膜枪",
    "aliases": [],
    "params": [
      {
        "name": "推力",
        "label": "推力",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 8,
        "max": 25,
        "step": 1,
        "unit": "kg",
        "defaultValue": 16
      },
      {
        "name": "振幅",
        "label": "振幅",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 6,
        "max": 16,
        "step": 1,
        "unit": "mm",
        "defaultValue": 10
      },
      {
        "name": "档位",
        "label": "档位",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 20,
        "step": 1,
        "unit": "档",
        "defaultValue": 6
      },
      {
        "name": "噪音",
        "label": "噪音",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 35,
        "max": 55,
        "step": 1,
        "unit": "dB",
        "defaultValue": 42
      },
      {
        "name": "电池容量",
        "label": "电池容量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1500,
        "max": 4000,
        "step": 100,
        "unit": "mAh",
        "defaultValue": 2500
      },
      {
        "name": "按摩头数量",
        "label": "按摩头数量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 4,
        "max": 8,
        "step": 1,
        "unit": "个",
        "defaultValue": 6
      },
      {
        "name": "重量",
        "label": "重量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 0.6,
        "max": 1.5,
        "step": 0.05,
        "unit": "kg",
        "defaultValue": 0.8
      },
      {
        "name": "智能压感",
        "label": "智能压感",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "个护健康",
    "subcategory": "美容仪",
    "aliases": [
      "美容仪/射频仪"
    ],
    "params": [
      {
        "name": "技术类型",
        "label": "技术类型",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "RF射频",
          "EMS微电流",
          "LED光疗"
        ],
        "defaultValue": [
          "RF",
          "EMS",
          "LED"
        ]
      },
      {
        "name": "档位",
        "label": "档位",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 10,
        "step": 1,
        "unit": "档",
        "defaultValue": 5
      },
      {
        "name": "温控范围",
        "label": "温控范围",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 35,
        "max": 45,
        "step": 0.5,
        "unit": "℃",
        "defaultValue": 40
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 60,
        "max": 180,
        "step": 10,
        "unit": "分钟",
        "defaultValue": 120
      },
      {
        "name": "防水",
        "label": "防水",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX4",
          "IPX5",
          "IPX7"
        ],
        "defaultValue": "IPX5"
      },
      {
        "name": "充电方式",
        "label": "充电方式",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "底座",
          "Type-C",
          "磁吸"
        ],
        "defaultValue": "磁吸"
      },
      {
        "name": "智能提醒",
        "label": "智能提醒",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "冷敷模式",
        "label": "冷敷模式",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "个护健康",
    "subcategory": "脱毛仪",
    "aliases": [],
    "params": [
      {
        "name": "灯头寿命",
        "label": "灯头寿命",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 20,
        "max": 99,
        "step": 5,
        "unit": "万次",
        "defaultValue": 50
      },
      {
        "name": "能量密度",
        "label": "能量密度",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 8,
        "step": 0.5,
        "unit": "J/cm²",
        "defaultValue": 5
      },
      {
        "name": "档位",
        "label": "档位",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 10,
        "step": 1,
        "unit": "档",
        "defaultValue": 5
      },
      {
        "name": "出光速度",
        "label": "出光速度",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 0.5,
        "max": 2.5,
        "step": 0.1,
        "unit": "秒/次",
        "defaultValue": 1
      },
      {
        "name": "冰感功能",
        "label": "冰感功能",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "肤色识别",
        "label": "肤色识别",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "灯头面积",
        "label": "灯头面积",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 7,
        "step": 0.5,
        "unit": "cm²",
        "defaultValue": 4.5
      },
      {
        "name": "连闪模式",
        "label": "连闪模式",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "个护健康",
    "subcategory": "电子体温计",
    "aliases": [],
    "params": [
      {
        "name": "测量精度",
        "label": "测量精度",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 0.05,
        "max": 0.3,
        "step": 0.01,
        "unit": "℃",
        "defaultValue": 0.1
      },
      {
        "name": "响应时间",
        "label": "响应时间",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1,
        "max": 30,
        "step": 1,
        "unit": "秒",
        "defaultValue": 5
      },
      {
        "name": "测量方式",
        "label": "测量方式",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "腋下",
          "口腔",
          "耳温",
          "额温"
        ],
        "defaultValue": "额温"
      },
      {
        "name": "记忆组数",
        "label": "记忆组数",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 10,
        "max": 99,
        "step": 1,
        "unit": "组",
        "defaultValue": 30
      },
      {
        "name": "发烧提醒",
        "label": "发烧提醒",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "屏幕类型",
        "label": "屏幕类型",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "LED",
          "背光LCD"
        ],
        "defaultValue": "背光LCD"
      },
      {
        "name": "APP记录",
        "label": "APP记录",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "多用户",
        "label": "多用户",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "个护健康",
    "subcategory": "血压计",
    "aliases": [
      "血压计/血糖仪"
    ],
    "params": [
      {
        "name": "测量方式",
        "label": "测量方式",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "上臂式",
          "手腕式"
        ],
        "defaultValue": "上臂式"
      },
      {
        "name": "精度",
        "label": "精度",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "标准",
          "医疗级"
        ],
        "defaultValue": "医疗级"
      },
      {
        "name": "记忆组数",
        "label": "记忆组数",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 60,
        "max": 200,
        "step": 10,
        "unit": "组",
        "defaultValue": 120
      },
      {
        "name": "语音播报",
        "label": "语音播报",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "APP同步",
        "label": "APP同步",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "袖带适配",
        "label": "袖带适配",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "标准22-32cm",
          "大号32-42cm"
        ],
        "defaultValue": "标准22-32cm"
      },
      {
        "name": "充电方式",
        "label": "充电方式",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "电池",
          "USB充电"
        ],
        "defaultValue": "USB充电"
      },
      {
        "name": "不规则脉检测",
        "label": "不规则脉检测",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "个护健康",
    "subcategory": "体脂秤",
    "aliases": [],
    "params": [
      {
        "name": "测量项目",
        "label": "测量项目",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 10,
        "max": 30,
        "step": 1,
        "unit": "项",
        "defaultValue": 20
      },
      {
        "name": "精度",
        "label": "精度",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 0.01,
        "max": 0.1,
        "step": 0.01,
        "unit": "kg",
        "defaultValue": 0.05
      },
      {
        "name": "称重范围",
        "label": "称重范围",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "0.2-150",
          "180",
          "200kg"
        ],
        "defaultValue": "0.2-180kg"
      },
      {
        "name": "APP同步",
        "label": "APP同步",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "蓝牙",
          "Wi-Fi"
        ],
        "defaultValue": "Wi-Fi"
      },
      {
        "name": "多用户识别",
        "label": "多用户识别",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "屏幕显示",
        "label": "屏幕显示",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "隐藏",
          "LED",
          "彩屏"
        ],
        "defaultValue": "LED"
      },
      {
        "name": "充电方式",
        "label": "充电方式",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "电池",
          "USB"
        ],
        "defaultValue": "USB"
      },
      {
        "name": "材质",
        "label": "材质",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "钢化玻璃",
          "ITO镀膜"
        ],
        "defaultValue": "钢化玻璃+ITO"
      }
    ]
  },
  {
    "category": "母婴用品",
    "subcategory": "婴儿监视器",
    "aliases": [],
    "params": [
      {
        "name": "分辨率",
        "label": "分辨率",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "720P",
          "1080P",
          "2K"
        ],
        "defaultValue": "1080P"
      },
      {
        "name": "夜视功能",
        "label": "夜视功能",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "红外",
          "全彩"
        ],
        "defaultValue": "红外"
      },
      {
        "name": "云台",
        "label": "云台",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "固定",
          "水平",
          "全景"
        ],
        "defaultValue": "全景"
      },
      {
        "name": "传输方式",
        "label": "传输方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "Wi-Fi",
          "FHSS"
        ],
        "defaultValue": "Wi-Fi"
      },
      {
        "name": "双向对讲",
        "label": "双向对讲",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "啼哭检测",
        "label": "啼哭检测",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "温湿度监测",
        "label": "温湿度监测",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 6,
        "max": 24,
        "step": 1,
        "unit": "小时",
        "defaultValue": 12
      }
    ]
  },
  {
    "category": "母婴用品",
    "subcategory": "电动吸奶器",
    "aliases": [
      "吸奶器"
    ],
    "params": [
      {
        "name": "吸力档位",
        "label": "吸力档位",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 5,
        "max": 15,
        "step": 1,
        "unit": "档",
        "defaultValue": 9
      },
      {
        "name": "模式",
        "label": "模式",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "单模式",
          "双模式",
          "变频"
        ],
        "defaultValue": "变频"
      },
      {
        "name": "噪音",
        "label": "噪音",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 35,
        "max": 50,
        "step": 1,
        "unit": "dB",
        "defaultValue": 40
      },
      {
        "name": "电池容量",
        "label": "电池容量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 800,
        "max": 2500,
        "step": 100,
        "unit": "mAh",
        "defaultValue": 1500
      },
      {
        "name": "充电方式",
        "label": "充电方式",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "充电器",
          "Type-C",
          "底座"
        ],
        "defaultValue": "Type-C"
      },
      {
        "name": "材质",
        "label": "材质",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "PP",
          "硅胶",
          "PPSU"
        ],
        "defaultValue": "PPSU"
      },
      {
        "name": "记忆功能",
        "label": "记忆功能",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "便携性",
        "label": "便携性",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "家用",
          "便携",
          "穿戴式"
        ],
        "defaultValue": "穿戴式"
      }
    ]
  },
  {
    "category": "母婴用品",
    "subcategory": "智能温奶器",
    "aliases": [],
    "params": [
      {
        "name": "控温精度",
        "label": "控温精度",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 0.5,
        "max": 3,
        "step": 0.5,
        "unit": "℃",
        "defaultValue": 1
      },
      {
        "name": "加热方式",
        "label": "加热方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "水浴",
          "无水",
          "蒸汽"
        ],
        "defaultValue": "水浴"
      },
      {
        "name": "兼容瓶型",
        "label": "兼容瓶型",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "宽口",
          "标准",
          "通用"
        ],
        "defaultValue": "通用"
      },
      {
        "name": "定时功能",
        "label": "定时功能",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "保温时长",
        "label": "保温时长",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 6,
        "max": 24,
        "step": 1,
        "unit": "小时",
        "defaultValue": 12
      },
      {
        "name": "消毒功能",
        "label": "消毒功能",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "APP控制",
        "label": "APP控制",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "防干烧",
        "label": "防干烧",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "母婴用品",
    "subcategory": "儿童学习平板",
    "aliases": [],
    "params": [
      {
        "name": "屏幕尺寸",
        "label": "屏幕尺寸",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 7,
        "max": 11,
        "step": 0.5,
        "unit": "英寸",
        "defaultValue": 10
      },
      {
        "name": "护眼认证",
        "label": "护眼认证",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "莱茵",
          "国家AA"
        ],
        "defaultValue": "莱茵"
      },
      {
        "name": "内存",
        "label": "内存",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "3GB",
          "4GB",
          "6GB",
          "8GB"
        ],
        "defaultValue": "6GB"
      },
      {
        "name": "存储",
        "label": "存储",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "32GB",
          "64GB",
          "128GB",
          "256GB"
        ],
        "defaultValue": "128GB"
      },
      {
        "name": "家长管控",
        "label": "家长管控",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "学习资源",
        "label": "学习资源",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "小学",
          "初高中",
          "全学段"
        ],
        "defaultValue": "全学段"
      },
      {
        "name": "距离提醒",
        "label": "距离提醒",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 6,
        "max": 15,
        "step": 0.5,
        "unit": "小时",
        "defaultValue": 10
      }
    ]
  },
  {
    "category": "母婴用品",
    "subcategory": "婴儿推车",
    "aliases": [],
    "params": [
      {
        "name": "重量",
        "label": "重量",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 5,
        "max": 15,
        "step": 0.5,
        "unit": "kg",
        "defaultValue": 8
      },
      {
        "name": "折叠方式",
        "label": "折叠方式",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "手动",
          "一键折叠"
        ],
        "defaultValue": "一键折叠"
      },
      {
        "name": "承重",
        "label": "承重",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 15,
        "max": 25,
        "step": 1,
        "unit": "kg",
        "defaultValue": 20
      },
      {
        "name": "适用月龄",
        "label": "适用月龄",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "0-36个月",
          "6-36个月"
        ],
        "defaultValue": "0-36个月"
      },
      {
        "name": "减震类型",
        "label": "减震类型",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "弹簧",
          "液压",
          "四轮独立"
        ],
        "defaultValue": "四轮独立"
      },
      {
        "name": "座椅换向",
        "label": "座椅换向",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "手动",
          "单手旋转"
        ],
        "defaultValue": "单手旋转"
      },
      {
        "name": "遮阳篷",
        "label": "遮阳篷",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "半篷",
          "全篷",
          "加长"
        ],
        "defaultValue": "加长"
      },
      {
        "name": "置物篮",
        "label": "置物篮",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "小",
          "大"
        ],
        "defaultValue": "大"
      }
    ]
  },
  {
    "category": "母婴用品",
    "subcategory": "安全座椅",
    "aliases": [
      "儿童安全座椅"
    ],
    "params": [
      {
        "name": "安全认证",
        "label": "安全认证",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "3C",
          "ECE",
          "i-Size"
        ],
        "defaultValue": "i-Size"
      },
      {
        "name": "适用体重",
        "label": "适用体重",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 0,
        "max": 36,
        "step": 0.5,
        "unit": "kg",
        "defaultValue": 0
      },
      {
        "name": "安装方式",
        "label": "安装方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "安全带",
          "ISOFIX",
          "支撑腿"
        ],
        "defaultValue": [
          "ISOFIX",
          "支撑腿"
        ]
      },
      {
        "name": "旋转功能",
        "label": "旋转功能",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "360度旋转"
        ],
        "defaultValue": "360度旋转"
      },
      {
        "name": "侧撞保护",
        "label": "侧撞保护",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "面料",
        "label": "面料",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "普通",
          "透气",
          "阻燃"
        ],
        "defaultValue": "阻燃"
      },
      {
        "name": "头枕调节",
        "label": "头枕调节",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "3档",
          "5档",
          "无极"
        ],
        "defaultValue": "无极"
      },
      {
        "name": "拆卸清洗",
        "label": "拆卸清洗",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "支持",
          "不支持"
        ],
        "defaultValue": "支持"
      }
    ]
  },
  {
    "category": "母婴用品",
    "subcategory": "早教机器人",
    "aliases": [],
    "params": [
      {
        "name": "适合年龄",
        "label": "适合年龄",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 0,
        "max": 12,
        "step": 0.5,
        "unit": "岁",
        "defaultValue": 3
      },
      {
        "name": "内容资源",
        "label": "内容资源",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "基础",
          "绘本",
          "英语",
          "多学科"
        ],
        "defaultValue": "英语+绘本"
      },
      {
        "name": "交互方式",
        "label": "交互方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "语音",
          "触屏",
          "绘本识别"
        ],
        "defaultValue": [
          "语音",
          "触屏"
        ]
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 10,
        "step": 0.5,
        "unit": "小时",
        "defaultValue": 6
      },
      {
        "name": "联网方式",
        "label": "联网方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "Wi-Fi",
          "4G"
        ],
        "defaultValue": "Wi-Fi"
      },
      {
        "name": "屏幕",
        "label": "屏幕",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无屏",
          "2寸",
          "5寸",
          "7寸"
        ],
        "defaultValue": "5寸"
      },
      {
        "name": "材质安全",
        "label": "材质安全",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "食品级硅胶",
          "ABS"
        ],
        "defaultValue": "食品级硅胶"
      },
      {
        "name": "家长端APP",
        "label": "家长端APP",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "母婴用品",
    "subcategory": "儿童手表",
    "aliases": [],
    "params": [
      {
        "name": "定位方式",
        "label": "定位方式",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "GPS",
          "北斗",
          "Wi-Fi",
          "基站"
        ],
        "defaultValue": [
          "GPS",
          "北斗",
          "Wi-Fi"
        ]
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX4",
          "IPX7",
          "IPX8"
        ],
        "defaultValue": "IPX8"
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 2,
        "max": 7,
        "step": 0.5,
        "unit": "天",
        "defaultValue": 4
      },
      {
        "name": "通话方式",
        "label": "通话方式",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "2G",
          "4G VoLTE"
        ],
        "defaultValue": "4G VoLTE"
      },
      {
        "name": "屏幕类型",
        "label": "屏幕类型",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "OLED",
          "AMOLED"
        ],
        "defaultValue": "AMOLED"
      },
      {
        "name": "摄像头",
        "label": "摄像头",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "单摄",
          "双摄"
        ],
        "defaultValue": "双摄"
      },
      {
        "name": "电子围栏",
        "label": "电子围栏",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "学习功能",
        "label": "学习功能",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "户外装备",
    "subcategory": "运动相机",
    "aliases": [],
    "params": [
      {
        "name": "视频分辨率",
        "label": "视频分辨率",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "1080P",
          "4K",
          "5.3K",
          "6K"
        ],
        "defaultValue": "4K"
      },
      {
        "name": "防抖等级",
        "label": "防抖等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "电子",
          "增强",
          "地平线锁定"
        ],
        "defaultValue": "地平线锁定"
      },
      {
        "name": "防水深度",
        "label": "防水深度",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 5,
        "max": 60,
        "step": 5,
        "unit": "m",
        "defaultValue": 10
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 60,
        "max": 180,
        "step": 10,
        "unit": "分钟",
        "defaultValue": 90
      },
      {
        "name": "广角范围",
        "label": "广角范围",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 120,
        "max": 170,
        "step": 5,
        "unit": "度",
        "defaultValue": 155
      },
      {
        "name": "重量",
        "label": "重量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 80,
        "max": 180,
        "step": 5,
        "unit": "g",
        "defaultValue": 120
      },
      {
        "name": "裸机防水",
        "label": "裸机防水",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "是",
          "否"
        ],
        "defaultValue": "是"
      },
      {
        "name": "语音控制",
        "label": "语音控制",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "户外装备",
    "subcategory": "户外手表",
    "aliases": [],
    "params": [
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 5,
        "max": 90,
        "step": 1,
        "unit": "天",
        "defaultValue": 30
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "5ATM",
          "10ATM"
        ],
        "defaultValue": "10ATM"
      },
      {
        "name": "定位",
        "label": "定位",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "GPS",
          "北斗",
          "GLONASS"
        ],
        "defaultValue": [
          "GPS",
          "北斗"
        ]
      },
      {
        "name": "材质",
        "label": "材质",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "塑料",
          "不锈钢",
          "钛合金",
          "蓝宝石"
        ],
        "defaultValue": "钛合金+蓝宝石"
      },
      {
        "name": "地图导航",
        "label": "地图导航",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "无",
          "轨迹",
          "离线地图"
        ],
        "defaultValue": "离线地图"
      },
      {
        "name": "运动模式",
        "label": "运动模式",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 20,
        "max": 200,
        "step": 5,
        "unit": "种",
        "defaultValue": 100
      },
      {
        "name": "血氧监测",
        "label": "血氧监测",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "温度计",
        "label": "温度计",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "户外装备",
    "subcategory": "便携电源",
    "aliases": [
      "户外电源/移动电源"
    ],
    "params": [
      {
        "name": "容量",
        "label": "容量",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 5000,
        "max": 40000,
        "step": 500,
        "unit": "mAh",
        "defaultValue": 20000
      },
      {
        "name": "输出功率",
        "label": "输出功率",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 10,
        "max": 140,
        "step": 5,
        "unit": "W",
        "defaultValue": 65
      },
      {
        "name": "快充协议",
        "label": "快充协议",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "PD",
          "QC",
          "SCP"
        ],
        "defaultValue": [
          "PD",
          "QC"
        ]
      },
      {
        "name": "接口数量",
        "label": "接口数量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1,
        "max": 5,
        "step": 1,
        "unit": "个",
        "defaultValue": 3
      },
      {
        "name": "重量",
        "label": "重量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 150,
        "max": 800,
        "step": 10,
        "unit": "g",
        "defaultValue": 400
      },
      {
        "name": "无线充电",
        "label": "无线充电",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "太阳能",
        "label": "太阳能",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "无"
      },
      {
        "name": "数显屏幕",
        "label": "数显屏幕",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "户外装备",
    "subcategory": "露营灯",
    "aliases": [
      "露营灯/头灯"
    ],
    "params": [
      {
        "name": "亮度",
        "label": "亮度",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 100,
        "max": 2000,
        "step": 50,
        "unit": "lm",
        "defaultValue": 800
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 4,
        "max": 80,
        "step": 2,
        "unit": "小时",
        "defaultValue": 20
      },
      {
        "name": "电源方式",
        "label": "电源方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "电池",
          "充电",
          "太阳能"
        ],
        "defaultValue": "充电"
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX4",
          "IPX5",
          "IPX7"
        ],
        "defaultValue": "IPX7"
      },
      {
        "name": "色温调节",
        "label": "色温调节",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "单色",
          "双色",
          "无极"
        ],
        "defaultValue": "无极"
      },
      {
        "name": "悬挂方式",
        "label": "悬挂方式",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "手提",
          "磁吸",
          "挂钩"
        ],
        "defaultValue": "挂钩"
      },
      {
        "name": "SOS模式",
        "label": "SOS模式",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "充电宝功能",
        "label": "充电宝功能",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "户外装备",
    "subcategory": "GPS导航仪",
    "aliases": [],
    "params": [
      {
        "name": "屏幕尺寸",
        "label": "屏幕尺寸",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 2.6,
        "max": 7,
        "step": 0.2,
        "unit": "英寸",
        "defaultValue": 5
      },
      {
        "name": "卫星系统",
        "label": "卫星系统",
        "controlType": "multiSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "GPS",
          "北斗",
          "GLONASS",
          "伽利略"
        ],
        "defaultValue": [
          "GPS",
          "北斗",
          "GLONASS",
          "伽利略"
        ]
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 8,
        "max": 50,
        "step": 1,
        "unit": "小时",
        "defaultValue": 25
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX5",
          "IPX7",
          "IPX8"
        ],
        "defaultValue": "IPX7"
      },
      {
        "name": "地图",
        "label": "地图",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "基础",
          "等高线",
          "3D"
        ],
        "defaultValue": "等高线"
      },
      {
        "name": "内存",
        "label": "内存",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "8GB",
          "16GB",
          "32GB"
        ],
        "defaultValue": "16GB"
      },
      {
        "name": "高度计",
        "label": "高度计",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "无线同步",
        "label": "无线同步",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "户外装备",
    "subcategory": "对讲机",
    "aliases": [],
    "params": [
      {
        "name": "通话距离",
        "label": "通话距离",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 1,
        "max": 15,
        "step": 0.5,
        "unit": "km",
        "defaultValue": 8
      },
      {
        "name": "频道数量",
        "label": "频道数量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 8,
        "max": 128,
        "step": 8,
        "unit": "个",
        "defaultValue": 32
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 8,
        "max": 48,
        "step": 2,
        "unit": "小时",
        "defaultValue": 24
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX4",
          "IPX5",
          "IPX7"
        ],
        "defaultValue": "IPX7"
      },
      {
        "name": "降噪技术",
        "label": "降噪技术",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "紧急报警",
        "label": "紧急报警",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "重量",
        "label": "重量",
        "controlType": "continuousSlider",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 80,
        "max": 300,
        "step": 10,
        "unit": "g",
        "defaultValue": 180
      },
      {
        "name": "免提通话",
        "label": "免提通话",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "户外装备",
    "subcategory": "防水背包",
    "aliases": [
      "登山包/背包"
    ],
    "params": [
      {
        "name": "容量",
        "label": "容量",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 15,
        "max": 80,
        "step": 5,
        "unit": "L",
        "defaultValue": 30
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX4",
          "IPX6",
          "IPX8"
        ],
        "defaultValue": "IPX6"
      },
      {
        "name": "重量",
        "label": "重量",
        "controlType": "continuousSlider",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 400,
        "max": 2000,
        "step": 50,
        "unit": "g",
        "defaultValue": 900
      },
      {
        "name": "材质",
        "label": "材质",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "尼龙",
          "TPU",
          "PVC夹网"
        ],
        "defaultValue": "TPU"
      },
      {
        "name": "背负系统",
        "label": "背负系统",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "基础",
          "透气",
          "人体工学"
        ],
        "defaultValue": "人体工学"
      },
      {
        "name": "气密拉链",
        "label": "气密拉链",
        "controlType": "switch",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "外挂系统",
        "label": "外挂系统",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      },
      {
        "name": "反光条",
        "label": "反光条",
        "controlType": "switch",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  },
  {
    "category": "户外装备",
    "subcategory": "应急手电",
    "aliases": [],
    "params": [
      {
        "name": "亮度",
        "label": "亮度",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 200,
        "max": 5000,
        "step": 50,
        "unit": "lm",
        "defaultValue": 2000
      },
      {
        "name": "续航",
        "label": "续航",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 3,
        "max": 50,
        "step": 1,
        "unit": "小时",
        "defaultValue": 15
      },
      {
        "name": "射程",
        "label": "射程",
        "controlType": "continuousSlider",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "min": 100,
        "max": 500,
        "step": 10,
        "unit": "m",
        "defaultValue": 300
      },
      {
        "name": "电源方式",
        "label": "电源方式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "电池",
          "充电",
          "手摇"
        ],
        "defaultValue": "充电+电池"
      },
      {
        "name": "防水等级",
        "label": "防水等级",
        "controlType": "discreteSelect",
        "defaultWeight": 5,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "IPX4",
          "IPX6",
          "IPX8"
        ],
        "defaultValue": "IPX8"
      },
      {
        "name": "材质",
        "label": "材质",
        "controlType": "discreteSelect",
        "defaultWeight": 3,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "铝合金",
          "不锈钢",
          "钛合金"
        ],
        "defaultValue": "铝合金"
      },
      {
        "name": "调光模式",
        "label": "调光模式",
        "controlType": "discreteSelect",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "单档",
          "3档",
          "无极"
        ],
        "defaultValue": "无极"
      },
      {
        "name": "SOS/爆闪",
        "label": "SOS/爆闪",
        "controlType": "switch",
        "defaultWeight": 4,
        "hint": "滑块范围为常见规格建议值，特殊产品可直接输入超出范围的数值；保存后会作为用户自定义配置参与仿真。",
        "options": [
          "有",
          "无"
        ],
        "defaultValue": "有"
      }
    ]
  }
];

export function productSubcategoriesForMajor(category: string): string[] {
  return [...((PRODUCT_CATEGORY_MAP as Record<string, readonly string[]>)[category] || [])];
}

export function normalizeProductSubcategory(value: string): string {
  return value.trim().replace(/[??]/g, (char) => (char === "?" ? "(" : ")")).replace(/\s+/g, "").toLowerCase();
}

export function findProductParamTemplate(category: string, subcategory: string): ProductSubcategoryTemplate | undefined {
  const normalized = normalizeProductSubcategory(subcategory);
  return PRODUCT_PARAM_TEMPLATES.find((item) => {
    if (item.category !== category) return false;
    const names = [item.subcategory, ...item.aliases];
    return names.some((name) => normalizeProductSubcategory(name) === normalized);
  });
}
