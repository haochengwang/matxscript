#pragma once

#include "matxscript/runtime/container/string_view.h"

#include <string>
#include <vector>

namespace matxscript {
namespace runtime {

class RockflowContext {
public:
    RockflowContext(const matxscript::runtime::Any&) {}

    virtual int64_t GetInt(const std::string& attr, int64_t default_value) const {
        return 0;
    }

    virtual double GetDouble(const std::string& attr, double default_value) const {
        return 0.0;
    }

    virtual matxscript::runtime::string_view GetString(const std::string& attr, const matxscript::runtime::string_view& default_value) const {
        return matxscript::runtime::string_view{};
    }

    virtual matxscript::runtime::FTList<int64_t> GetIntList(const std::string& attr) const {
        return matxscript::runtime::FTList<int64_t>{};
    }

    virtual matxscript::runtime::FTList<double> GetDoubleList(const std::string& attr) const {
        return matxscript::runtime::FTList<double>{};
    }

    virtual matxscript::runtime::FTList<matxscript::runtime::string_view>
        GetStringList(const std::string& attr) const {
        return matxscript::runtime::FTList<matxscript::runtime::string_view>{};
    }

    virtual int SetInt(const std::string& attr, int value) const {
        return 0;
    }
};

}  // namespace runtime
}  // namespace matxscript
