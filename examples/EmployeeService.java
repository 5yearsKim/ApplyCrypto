package com.mybatis.service;

import java.util.List;
import java.util.Map;

import com.mybatis.beans.User;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.mybatis.beans.Department;
import com.mybatis.beans.Employee;
import com.mybatis.dao.DepartmentMapper;
import com.mybatis.dao.EmployeeMapper;

import k_sign.CryptoService;

@Service
public class EmployeeService {

	@Autowired
	private EmployeeMapper employeeMapper;

	@Autowired
	private DepartmentMapper deptMapper;
	public List<Employee> getEmps(){
		List<Employee> employees = employeeMapper.getEmps();
		for (Employee employee : employees) {
			employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
		}
		return employees;
	}

	public void delete(Integer id) {
		// TODO Auto-generated method stub
		employeeMapper.deleteEmpById(id);

	}

	public void update(Employee employee)
	{
		employee.setJuminNumber(k_sign.CryptoService.encrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
		employeeMapper.updateEmp(employee);
	}
	public void save(Employee employee) {
		// TODO Auto-generated method stub
		Department dept = deptMapper.getDeptById(employee.getDept().getId());
		employee.setDept(dept);
		employee.setJuminNumber(k_sign.CryptoService.encrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
		employeeMapper.addEmp(employee);

	}

	public Employee getEmpById(Integer id) {
		Employee employee = employeeMapper.getEmpById(id);
		employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
		return employee;
	}

	public List<Employee> getEmpsByPage(Integer pageIndex,Integer size) {
		List<Employee> employees = employeeMapper.getEmpsByPage(pageIndex,size);
		for (Employee employee : employees) {
			employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
		}
		return employees;
	}
	public int getLength()
	{
		return employeeMapper.getLength();
	}

	public List<Employee>  query(String condition) {
		List<Employee> employees = employeeMapper.query(condition);
		for (Employee employee : employees) {
			employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
		}
		return employees;
	}

	public List<Map<String, Object>> getDatas() {
		// TODO Auto-generated method stub
		List<Map<String, Object>> data = employeeMapper.getDatas();
		for (Map<String, Object> map : data) {
			map.put("juminNumber", k_sign.CryptoService.decrypt(map.get("juminNumber").toString(), k_sign.CryptoService.K_SIGN_SSM));
		}
		return data;
	}
	public List<Map<String, Object>> getPer() {
		// TODO Auto-generated method stub
		List<Map<String, Object>> per = employeeMapper.getPer();
		for (Map<String, Object> map : per) {
			map.put("juminNumber", k_sign.CryptoService.decrypt(map.get("juminNumber").toString(), k_sign.CryptoService.K_SIGN_SSM));
		}
		return per;
	}

	public User login(User user) {
		User u = employeeMapper.login(user.getUserName(),user.getPassword());
		return u;
	}
	public User getUserInfo(User user) {
		User u = employeeMappeer.getUserInfo(user.getUserName(),user.getPassword());
		return u;
	}
}
